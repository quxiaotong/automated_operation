import boto3
import redis
import time
from zabbix.api import ZabbixAPI
import json
from ansible.executor.playbook_executor import PlaybookExecutor
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
import ansible.constants as C

#zabbix服务器自动添加删除维护，并且自动添加执行ansible-playbook自动安装客户端
pool = redis.ConnectionPool(host="54.223.98.251", port=6379, db=10)
redis_cli = redis.Redis(connection_pool=pool)
zapi = ZabbixAPI(url='http://zabbix.guokr.com', user='admin', password='zabbix')
Ec2_keys = ["InstanceId", "PrivateIpAddress", "State", "Tags"]
already_maintenance = zapi.do_request("maintenance.get")["result"]
ansible_hosts_file = "/data/ansible/test_playbook_api_host"
playbook_yaml_path = '/data/ansible/test.yml'


class ansible_playbook(object):
    def __init__(self,ansible_hostsfile):
        self.ansible_hostsfile = ansible_hostsfile
        self.loader = DataLoader()
        self.inventory = InventoryManager(loader=self.loader, sources=self.ansible_hostsfile)
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)
        self.Options = namedtuple('Options',
                    [ 'connection',
                     'remote_user',
                     'ask_sudo_pass',
                     'verbosity',
                     'ack_pass',
                     'module_path',
                     'forks',
                     'become',
                     'become_method',
                     'become_user',
                     'check',
                     'listhosts',
                     'listtasks',
                     'listtags',
                     'syntax',
                     'sudo_user',
                     'sudo',
                     'diff'])
        self.options = self.Options(
                connection='smart',
                remote_user='root',
                ack_pass=None,
                sudo_user='root',
                forks=200,
                sudo='yes',
                ask_sudo_pass=False,
                verbosity=5,
                module_path=None,
                become=True,
                become_method='su',
                become_user='root',
                check=None,
                listhosts=None,
                listtasks=None,
                listtags=None,
                syntax=None,
                diff=False)
    def playexecutor(self,playbook_yaml_path):
        playbook = PlaybookExecutor(playbooks=[playbook_yaml_path],
                      inventory=self.inventory,
                      variable_manager=self.variable_manager,
                      loader=self.loader,
                      options=self.options,
                      passwords=None)
        return playbook


def ec2_collect():
    ec2_client = boto3.client('ec2')
    EC2 = []
    Ec2_Item = []
    aws_ec2_stop = []
    aws_ec2_all = []
    ec2_res = ec2_client.describe_instances()
    if not ec2_res:
        return
    for reservation in ec2_res['Reservations']:
        for instance in reservation['Instances']:
            Ec2_Item.append(instance)
    for i in Ec2_Item:
        data = {key: i.get(key, '') for key in Ec2_keys}
        EC2.append(data)
    for field_change in EC2:
        field_change["State"] = field_change["State"]["Name"]
        for i in field_change["Tags"]:
            if i["Key"] == "Name":
                field_change["Name"] = i["Value"]
        field_change.pop("Tags")
    for ec2 in EC2:
        if ec2["State"] == "stopped":
            aws_ec2_stop.append(ec2["PrivateIpAddress"])
        aws_ec2_all.append(ec2["PrivateIpAddress"])

    return aws_ec2_stop, aws_ec2_all

def ec2_redis():
    aws_ec2_stop, aws_ec2_all = ec2_collect()
    try:
        r_ec2_stop = set(eval(redis_cli.get("ec2_stopped").decode()))
        r_ec2_all = set(eval(redis_cli.get("ec2_alling").decode()))

        ec2_add = set(aws_ec2_all) - r_ec2_all
        ec2_del = r_ec2_all - set(aws_ec2_all)

        ec2_stop_add = set(aws_ec2_stop) - r_ec2_stop
        ec2_stop_del = r_ec2_stop - set(aws_ec2_stop)
        ec2_stop_continue = r_ec2_stop & set(aws_ec2_stop)
    except Exception as e:
        redis_cli.mset(ec2_stopped=aws_ec2_stop,ec2_alling=aws_ec2_all)
        ec2_add, ec2_del, ec2_stop_add, ec2_stop_del, ec2_stop_continue = [],[],[],[],[]
        return ec2_add, ec2_del, ec2_stop_add, ec2_stop_del, ec2_stop_continue
    redis_cli.mset(ec2_stopped=aws_ec2_stop,ec2_alling=aws_ec2_all)
    return ec2_add, ec2_del, ec2_stop_add, ec2_stop_del, ec2_stop_continue


def ec2_zabbix():
    ec2_add, ec2_del, ec2_stop_add, ec2_stop_del, ec2_stop_continue = ec2_redis()
    time_now = int(time.time())
    time_till = time_now + 86400
    print(ec2_add, ec2_del, ec2_stop_add, ec2_stop_del, ec2_stop_continue)
    for ec2_ip in ec2_del:
        try:
            ec2_id = zapi.do_request("hostinterface.get",{
            'filter':{"ip":ec2_ip},
            "output":['hostid']
        })["result"][0]["hostid"]
            zapi.do_request("host.delete",[ec2_id])
        except Exception:
            continue

    for ec2_ip in ec2_stop_add:
        try:
            ec2_id = zapi.do_request("hostinterface.get",{
            'filter':{"ip":ec2_ip},
            "output":['hostid']
        })["result"][0]["hostid"]
            zapi.do_request("maintenance.create",{
            "name":ec2_ip,
            "active_since":time_now,
            "active_till":time_till,
            "hostids":[ec2_id],
            "timeperiods": [{
                "timeperiod_type": 0,
                "start_date":time_now,
                "period":86400,
            }]
        })
        except Exception as e:
            print(e)
            continue

    for ec2_ip in ec2_stop_del:
        for maintenance in already_maintenance:
            if ec2_ip == maintenance["name"]:
                zapi.do_request("maintenance.delete",[maintenance["maintenanceid"]])

    for ec2_ip in ec2_stop_continue:
        for maintenance in already_maintenance:
            if ec2_ip == maintenance["name"] and int(maintenance["active_till"]) < int(time.time()):
                zapi.do_request("maintenance.delete",[maintenance["maintenanceid"]])
                zapi.do_request("maintenance.create",{
                    "name":ec2_ip,
                    "active_since":time_now,
                    "active_till":time_till,
                    "hostids":[ec2_id],
                    "timeperiods": [{
                        "timeperiod_type": 0,
                        "start_date":time_now,
                        "period":86400,
                    }]
                })

    if ec2_add:
        hostfile = open(ansible_hosts_file, 'w+', encoding='utf-8')
        for ec2_ip in ec2_add:
            hostfile.write(ec2_ip+"\n")
        hostfile.close()
        #wait for aws's server start-up
        time.sleep(20)
        ansible_playbook_ins = ansible_playbook(ansible_hosts_file)
        playbook_ins = ansible_playbook_ins.playexecutor(playbook_yaml_path)
        try:
            res = playbook_ins.run()
        except Exception as e:
            print(e)
        if res:
            print("playbook execut failly")

while True:
        ec2_zabbix()
        time.sleep(60)
