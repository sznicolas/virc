#!/usr/bin/python

#
# virc mkstats.py
# Nicolas Schmeltz , 2018
#
# Connects to the mongodb collections storing the trades on a pair
# 
# Generates redis data :
#  cb:mkt:tick:<pair> is a string, contains the last price traded 
#  cb:mkt:change:<pair> contains a json object :
# { period : // see lperiods dict 
#    {
#    "volume": float, 
#    "average": float, 
#    "oc%": float, // % change in the period
#    "high": float, 
#    "range": float,
#    "low": float,
#    "close": float,
#    "open": float
#    },
#
# TODO :
# - calculate more statistics (RSI, ...)
# - map-reduce old data

import redis, time, json, os
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timedelta
from pprint import pprint

redissrv = "redis"
redisport = 6379
mongosvr = "mongo"
mongoport = "27017"
database_name = "cryptomarket_db"

looptime = int(os.environ.get('analyst_refresh', 2))

rds = redis.StrictRedis(host=redissrv, port=redisport, db=0)

mongo_client = MongoClient('mongodb://' + mongosvr +":" + mongoport + '/')
db = mongo_client[database_name]
collections = db.collection_names()
print "Starting Analyst. Pairs: ", collections

lastprice = None # used for the ticker, and the periodic changes
lperiods = { "last_24h": 24 * 60,
             "last_6h" : 6 * 60,
             "last_1h" : 60,
             "last_15m": 15 ,
             "last_5m" : 5,  
             "last_1m" : 1,
             "last_30s" : 0.5,
#             "last_10s" : 1/6  
           }

laststats_query = [
  { "$match" : { "isodate":{"$gt" : 9999999999 }}},
  {
    "$group" :
      { "_id" : "tot",
           "totprice" : { "$sum": { "$multiply": [ "$price", "$size" ] } },
           "volume" : { "$sum": "$size" },
           "high" : { "$max" : "$price"},
           "low"  : { "$min" : "$price"},
           "open" : { "$first" : "$price" },
           "close" : { "$last"  : "$price" },
           }, 
  },
  {
    "$project" : {
        "average" : { "$divide" : [ "$totprice", "$volume" ] } ,
        "volume" : "$volume",
        "high" : "$high", 
        "low"  : "$low" , 
        "open" :  "$open", 
        "close" :  "$close",
        "_id" : 0
    }
  }
  ]

def printstats():
    # Colors for output
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'
    # output some last periods to stdout
    now = datetime.utcnow()
    print "--------------"
    print "Volume low     high    %        range \t{}'s actual price: {}{}{} - {:02d}:{:02d}:{:02d}".format(
            collection, YELLOW, res["close"], ENDC, now.hour, now.minute, now.second)
    for d in ["last_1h", "last_15m", "last_5m", "last_1m", "last_30s"]:
         if stats.get(d):
             if (stats[d]["oc%"] < 0):
                 color = RED
             elif (stats[d]["oc%"] > 0 ):
                 color = GREEN
             else:
                 color = ENDC
             if (stats[d]["close"] is not None):
                 print "{:06.2f} {:06.2f} {:06.2f} {}{:+07.3f}{} {:5.2f} {}".format(
                         stats[d]['volume'], stats[d]['low'], stats[d]['high'],
                         color, stats[d]["oc%"], ENDC, stats[d]["range"], d)

if __name__ == "__main__":

    # set a translation between coinbase's products and collection's name:
    products={}
    cbproducts = []
    clast_id = {}
    for c in collections:
        p =  db[c].find_one()['product_id']
        products[c] = p
        products[p] = c
        cbproducts.append(p)
    rds.set("virc:convproducts", json.dumps(products))
    rds.set("virc:cb:products", json.dumps(cbproducts))

    while (True) :
        # calculate for all pairs
        for collection in collections:
            stats = {}
            # query for all periods
            for d in (lperiods):
                # adapt the query for the current time and the period
                laststats_query[0]['$match']['isodate']['$gt'] = datetime.utcnow() - timedelta(minutes = lperiods[d])
                try :
                    res = db.command("aggregate", collection , pipeline=laststats_query, cursor = {})["cursor"]["firstBatch"][0]
                except IndexError: # no data retreived ; no trade in this period or a problem somewhere ?
                    if (lastprice is None):
                        continue
                    res = {"volume":0, "low": None, "high": None, "average": None, 
                            "open": lastprice, "close": None, "oc%": 0, "range": 0}
                else:
                    res["oc%"] = (res['close'] - res['open']) *100 / res['open']
                    res["range"] = res['high'] - res['low']
                stats[d] = res
                
            stats["ticker"] = {"price": lastprice, "pair": products[collection]}

            # PUBSUB
            last_id = db[collection].find_one(sort=[('_id', DESCENDING)])['_id']
            if ( clast_id.get(collection) != last_id):
                rds.publish('cb:mkt:tick:pubsub', json.dumps({"type": "update", "data": stats}))
                clast_id[collection] = last_id

            # update market data if changed
            if ("last_15m" in stats):
                lastprice = stats["last_15m"]['close']
                if lastprice is None:
                    continue
            else:
                continue
            rdkey = "cb:mkt:tick:" + products[collection]
            rds.set(rdkey, lastprice)
            rds.expire(rdkey, looptime + 2)
            # last periods
            rds.set("cb:mkt:change:" + products[collection], json.dumps(stats)) 
            # printstats()
        # wait before next stats
        time.sleep(looptime)
