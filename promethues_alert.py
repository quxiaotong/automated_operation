# -*- coding: utf-8 -*-
import redis
import json
import requests
import sys
import pickle

pool =  redis.ConnectionPool(host="10.10.0.212", port=6379, db=1)
r = redis.Redis(connection_pool=pool)
corpsecret="mGVEjbq5-QokZp-givYJa0Bc9eJm4n6EKbz_EWS8PbM"
user="4"
sectionid="4"
agentid="1000009"
def senddata(corpsecret,user,sectionid,agentid,subject,content):

    corpid =  'ww73460d4b034fb644'   #CorpID是企业号的标识

    gettoken_url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=' + corpid + '&corpsecret=' + corpsecret
    try:
        token_file = requests.get(gettoken_url)
    except Exception as e:
        print(e)
    token_data = token_file.content.decode()
    token_json = json.loads(token_data)
    access_token = token_json['access_token']

    send_url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' + access_token

    send_values = {
        "touser":user,    #企业号中的用户帐号，如果配置不正常，将按部门发送。
        "toparty":sectionid,    #企业号中的部门id。
        "msgtype":"text", #消息类型。
        "agentid":agentid,    #企业号中的应用id。
        "text":{
            "content":subject + '\n' + content
           },
        "safe":"0"
        }
    send_data = json.dumps(send_values)
    try:
        send_request = requests.post(send_url, send_data)
    except Exception as e:
        print(e)
all_alarm_name = r.keys()
for alarm_name in all_alarm_name:
    alarm_name = alarm_name.decode()
    alarm_values = r.hgetall(alarm_name)
    try:
        if int(alarm_values["last30m".encode()].decode()):
            if int(r.hget(alarm_values,"cronalert").decode()) == 3:
                subject = "alertname: " + alarm_name + "报警关闭！"
                alert_message = "由于#" + alarm_name + "#报警共触发" + alarm_values["total".encode()].decode() + "$次，您未处理，我们将自动关闭次类报警！有问题联系管理员或去#alertmanager.guokr.net#报警平台查看此类报警！"
                content = str(alert_message)
                senddata(corpsecret, user, sectionid, agentid, subject, content)
                r.hincrby(alarm_name, "cronalert", amount=1)
            elif int(r.hget(alarm_values,"cronalert").decode()) > 3:
                r.hincrby(alarm_name, "cronalert", amount=1)
            else:
                subject = "alertname: " + alarm_name
                alert_message = "30分钟内#" + alarm_name + "#报警增加了$" + alarm_values["last30m".encode()].decode() + "$条，请处理！如果不重要请去#alertmanager.guokr.net#报警平台关掉此类报警!"
                content = str(alert_message)
                senddata(corpsecret, user, sectionid, agentid, subject, content)
                r.hset(alarm_name,"last30m",0)
                r.hincrby(alarm_name, "cronalert", amount=1)
        else:
                subject = "alertname: " + alarm_name
                alert_message = "报警#" + alarm_name + "#已恢复!"
                content = str(alert_message)
                senddata(corpsecret, user, sectionid, agentid, subject, content)
                r.delete(alarm_name)
    except Exception as e:
        print(e)









# -*- coding: utf-8 -*-
from flask import Flask
from flask import request
import json
import requests
import sys
import pickle
import redis
pool =  redis.ConnectionPool(host="54.223.98.251", port=6379, db=1)
r = redis.Redis(connection_pool=pool)


app = Flask(__name__)

def senddata(corpsecret,user,sectionid,agentid,subject,content):

    corpid =  'ww73460d4b034fb644'   #CorpID是企业号的标识

    gettoken_url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=' + corpid + '&corpsecret=' + corpsecret
    try:
        token_file = requests.get(gettoken_url)
    except Exception as e:
        print(e)
    token_data = token_file.content.decode()
    token_json = json.loads(token_data)
    access_token = token_json['access_token']

    send_url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' + access_token

    send_values = {
        "touser":user,    #企业号中的用户帐号，如果配置不正常，将按部门发送。
        "toparty":sectionid,    #企业号中的部门id。
        "msgtype":"text", #消息类型。
        "agentid":agentid,    #企业号中的应用id。
        "text":{
            "content":subject + '\n' + content
           },
        "safe":"0"
        }
    send_data = json.dumps(send_values)
    try:
        send_request = requests.post(send_url, send_data)
    except Exception as e:
        print(e)

@app.route("/prometheus", methods=['GET', 'POST', 'PUT'])
def prometheus_alarm():
    corpsecret = "mGVEjbq5-QokZp-givYJa0Bc9eJm4n6EKbz_EWS8PbM"
    user = "4"
    sectionid = "4"
    agentid = "1000009"
    alarm_data = eval(request.data.decode())
    try:
        for item in alarm_data["alerts"]:
            message = {}
            message["alertname"] = item["labels"]["alertname"]
            try:
                message["message"] = item["annotations"]["description"]
            except Exception as e:
                try:
                    message["message"] = item["annotations"]["message"]
                except Exception as e:
                    message["message"] = item["annotations"]
            message["level"] = item["labels"]["severity"]
            message["start_time"] = datetime.strftime((parser.parse(item["startsAt"]) + timedelta(hours=8)),"%Y.%m.%d %H:%M:%S")
            if  r.exists(message["alertname"]):
                r.hincrby(message["alertname"], "total", amount=1)
                r.hincrby(message["alertname"], "last30m", amount=1)
                #last30mtotal = int(r.hget(message["alertname"],"total").decode()) - int(r.hget(message["alertname"],"last30m").decode())
                #r.hset(message["alertname"],"last30mtotal",last30mtotal)
                r.hset(message["alertname"],"newalert",0)
            else:
                subject = "产生新报警: " + message["alertname"]
                alert_message = "信息: "+ message["message"] + "\n" + "级别: " + message["level"] + "\n" + "发生时间: " + message["start_time"]
                content = str(alert_message)
                senddata(corpsecret, user, sectionid, agentid, subject, content)
                r.hmset(message["alertname"],{"total":1,"last30m":1,"newalert":1,"alreadyalert":1,"cronalert":0})
    except Exception as e:
            print(e)
            return "500"
    return "201"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7777, debug=True)

