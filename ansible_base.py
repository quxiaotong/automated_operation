# -*- coding: utf-8 -*-
from gevent import monkey
import gevent
#monkey.patch_all()
import json
import shutil
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
import ansible.constants as C
import sys
import datetime
import psycopg2
from influxdb import InfluxDBClient
import time
from flask import current_app as app

ansible_hosts = "/tmp/ansible_hosts/disk_task"

def ansible_host_file(host):
    try:
        hostfile = open(ansible_hosts, 'w+', encoding='utf-8')
        #res_ec2 = DBsession.query(aws_model.Ec2.private_ip).filter(aws_model.Ec2.data_status is not False).all()
        res_ec2 = [host]
        for ec2 in res_ec2:
            #hostfile.write(ec2[0]+"\n")
            hostfile.write(ec2+"\n")
        hostfile.close()
    except Exception as e:
        print(e)
    else:
        return hostfile


class ResultCallback(CallbackBase):

    def __init__(self, display, options, result_function, task_name):
        super(ResultCallback,self).__init__(display, options)
        self.result_function = result_function
        self.task_name = task_name

    def v2_runner_on_unreachable(self, result):
        host = result._host.get_name()
        self.runner_on_unreachable(host, result._result)
        now = datetime.datetime.now()
        print(datetime.datetime.strftime(now,"%Y.%m.%d %H:%M:%S") + ":" + "this host " + host + " is not unreachable")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host = result._host
        now = datetime.datetime.now()
        print(datetime.datetime.strftime(now,"%Y.%m.%d %H:%M:%S") + ":" +  json.dumps({host.name: result._result, "error": ignore_errors}))

    def v2_runner_on_ok(self, result, **kwargs):
        try:
            handle_result = {}
            host = result._host
            res_task = {host.name:result._result}
            handle_result[host.name] = res_task[host.name]["stdout_lines"]
            self.result_function(host.name, handle_result)
        except Exception as e:
            now = datetime.datetime.now()
            print(datetime.datetime.strftime(now,"%Y.%m.%d %H:%M:%S") + ":" + e)


class AnsibleTask(object):
    def __init__(self,ansible_host):
        self.ansible_host = ansible_host
        res = ansible_host_file(self.ansible_host)
        if res is True:
            Options = namedtuple('Options', ['connection', 'module_path', 'forks', 'become',
                                             'become_method', 'become_user', 'check', 'diff'])
            self.options = Options(connection='ssh', module_path=sys.path, forks=100, become=None,
                                   become_method=None, become_user=None, check=False,diff=False)
            self.passwords = dict(vault_pass='secret')
            self.loader = DataLoader()
            self.inventory = InventoryManager(loader=self.loader, sources=ansible_hosts)
            self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)


    def play_task(self, module, args, task_name, function):
        results_callback = ResultCallback(display=None, options=None, task_name=task_name, result_function=function)

        play_source = dict(
                name=task_name,
                hosts='all',
                gather_facts='no',
                tasks=[
                    dict(action=dict(module=module, args=args), register='shell_out'),
                    #dict(action=dict(module='debug', args=dict(msg='{{shell_out.stdout}}')))
                 ]
            )
        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)
        tqm = None
        try:
            tqm = TaskQueueManager(
                      inventory=self.inventory,
                      variable_manager=self.variable_manager,
                      loader=self.loader,
                      options=self.options,
                      passwords=self.passwords,
                      stdout_callback=results_callback,
                  )
            result = tqm.run(play)
        except Exception as e:
            now = datetime.datetime.now()
            print(datetime.datetime.strftime(now,"%Y.%m.%d %H:%M:%S") + ":" + e)
        # else:
        #     return True
        finally:
            if tqm is not None:
                tqm.cleanup()
            shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)






