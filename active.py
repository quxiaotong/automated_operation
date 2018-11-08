#!/usr/local/bin/python3.5
import requests
import os
from os import environ
import etcd
import time
import logging

etcd_client = etcd.Client(host="10.10.0.212", port=2379)
logging.basicConfig(filename="active.log", level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

HOST_IP = os.popen("hostname --all-ip-addresses").read().split(" ")[0]
LISTEN_ON = str(environ.get("LISTEN_ON", 14500))
SERVICE_NAME = "cmdb"
PROJECT = "ops" #fantuan,guokr,ops


def active_probe():
    try:
        res = requests.get("http://127.0.0.1:%s%s" % (environ.get("LISTEN_ON", 14500), "/v1/active"))
    except Exception:
        logging.warning("%s prode failly on host %s" % (SERVICE_NAME, HOST_IP))
    else:
        res_code = int(res.status_code)
        if res_code == 200:
            try:
                etcd_client.write('/services/%s/address/%s:%s:%s' % (SERVICE_NAME, HOST_IP, LISTEN_ON,PROJECT), "%s:%s" % (HOST_IP, LISTEN_ON), ttl=60)
            except Exception:
                 logging.warning("%s register ectd failly on host %s" % (SERVICE_NAME, HOST_IP))
if __name__ == '__main__':
    while True:
        active_probe()
        time.sleep(15)