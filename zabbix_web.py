from zabbix.api import ZabbixAPI
from flask import current_app as app
import re
from datetime import datetime


zapi = ZabbixAPI(url=app.config['ZABBIX_URL'], user=app.config['ZABBIX_USER'], password=app.config['ZABBIX_PASSWORD'])
zab_server = zapi.do_request("host.get", {"search":{"name":"Zabbix server","host":"Zabbix server"}})
zab_hostid = zab_server["result"][0]["hostid"]
zab_web_apps_name = ["mooc", "science"]

def zab_web_itemids(app_name):
    app_item_id = {
        "download_speed": "",
        "response_time": "",
        "response_code": ""
    }
    app_itemids = zapi.do_request("item.get",
                    {"hostids": zab_hostid,
                     "webitems": "true",
                     "search": {
                         "key_": app_name,
                     },
                     })
    for item in app_itemids["result"]:
        if re.search("time", item["name"], flags=re.I):
            app_item_id["response_time"] = item["itemid"]
        elif re.search("code", item["name"], flags=re.I):
            app_item_id["response_code"] = item["itemid"]
        elif re.search("speed for step", item["name"], flags=re.I):
            app_item_id["download_speed"] = item["itemid"]
    return app_item_id


def zab_web_item_data(item_name, app_item_id, now_time, time_till):
    res_hist_data = []
    time_point = []
    data_point = []
    his_data = []
    item_id = app_item_id[item_name]
    history = zapi.history.get(itemids=item_id,
                           time_from=time_till,
                           time_till=now_time,
                           output='extend',
                           limit='100',
                           )
    if len(history):
        his_data = history
    else:
        history = zapi.history.get(itemids=item_id,
                               time_from=time_till,
                               time_till=now_time,
                               output='extend',
                               limit='100',
                               history=0,
                               )
        his_data = history
    for point in his_data:
        time_point.append(datetime.fromtimestamp(int(point['clock'])).strftime("%x %X"))
        data_point.append(point['value'])

    res_hist_data.append({"time": time_point, "data": data_point, "monitor_item": item_name})

    return res_hist_data

def zab_web_item_trend(item_name, app_item_id, now_time, time_till):
    item_id = app_item_id[item_name]
    trend_data = zapi.trend.get(itemids=item_id,
                   time_from=time_till,
                   time_till=now_time,
                    limit=1
                   )
    return trend_data[0]

