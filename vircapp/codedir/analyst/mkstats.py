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
#    "oc": float, // % change in the period
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

import utils

looptime = int(os.environ.get('analyst_refresh', 2))

#  TODO: find a better structure for periods

lperiods = [ 24 * 60,
             6 * 60,
             60,
             15 ,
             5,  
             1 ]
             # 0.5 ] # converted in json, name can't contain a dot.
           

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


if __name__ == "__main__":

    mongosvr = utils.mongosvr
    mongoport = utils.mongoport
    database_name = utils.database_name
    mongo_client = MongoClient('mongodb://' + mongosvr +":" + mongoport + '/')
    db = mongo_client[database_name]

    rds = utils.redis_connect()
    
    pairs = utils.Pairs(os.environ['pairs'].split()) # or  ['BTC-EUR', 'ETH-EUR'] 
    print "Starting Analyst. Pairs: ", pairs.keys()
    coll_last_id = {}
    lastprice = {} # used for the ticker, and the periodic changes

    while (True) :
        # calculate for all pairs
        for pair in pairs.keys():
            stats = {}
            collection = pairs.mdbpair(pair)
            # query for all periods
            for period in lperiods:
                stats[period] = {}
                # adapt the query for the current time and the period
                laststats_query[0]['$match']['isodate']['$gt'] = datetime.utcnow() - timedelta(minutes = period)
                try :
                    res = db.command("aggregate", collection, pipeline=laststats_query, cursor = {})["cursor"]["firstBatch"][0]
                except IndexError:
                # no data retreived ; no trade in this period or a problem somewhere ?
                    if (lastprice.get(pair) is None):
                        continue
                    res = {"volume":0, "low": None, "high": None, "average": None, 
                            "open": lastprice[pair], "close": None, "oc": 0, "range": 0}
                else:
                    res["oc"] = (res['close'] - res['open']) *100 / res['open']
                    res["range"] = res['high'] - res['low']
                stats["m" + str(period)] = res

            lastprice[pair] = stats['m60'].get('close')
            stats["ticker"] = {"price": lastprice[pair], "pair": pair}

            # PUBSUB
            last_id = db[collection].find_one(sort=[('_id', DESCENDING)])['_id']
            if ( coll_last_id.get(collection) != last_id):
                rds.publish('cb:mkt:tick:pubsub', json.dumps({"type": "update", "data": stats}))
                coll_last_id[collection] = last_id

            rdkey = "cb:mkt:tick:" + pair
            rds.set(rdkey, str(lastprice[pair]))
            rds.expire(rdkey, looptime + 2)
            # last periods
            rds.set("cb:mkt:change:" + pair, json.dumps(stats)) 
        # wait before next stats
        time.sleep(looptime)
