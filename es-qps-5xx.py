#!/usr/bin/python3.4
#_*_coding:utf-8 _*_
import sys
import datetime
from elasticsearch import Elasticsearch

time_till = sys.argv[1]

es = Elasticsearch(['http://elastic:changeme@180.76.142.197:9201'])

now_date = datetime.datetime.now().strftime("%Y.%m.%d")
def url_5xx(time_till):
     query_body={
       "query": {
         "bool": {
         "filter": [
            { "terms":  { "status": ["500","502","503","504"]}},
             { "range": { "@timestamp": { "gte": "now" + "-" + time_till }}}
         ]
         }
       }
     }
     count = es.count(index='fantuan_nginx-' + now_date, body=query_body)["count"]
     print(count)
url_5xx(time_till)
