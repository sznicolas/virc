#!/usr/bin/python3

#
# virc analyst.py
# Connects to the mongodb collections storing the trades on a pair
#  rewrites mkstats with Pandas use
# Nicolas Schmeltz , 2019
#
# Generates redis data :
#  cb:mkt:tick:<pair> is a string, contains the last price traded 
#  cb:mkt:change:<pair> contains a json object :
# { period : // see pperiods dict 
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
# - map-reduce mongo's old data

import redis, time, json, os
from datetime import datetime, timedelta
from dateutil import tz

from pymongo import MongoClient, DESCENDING
from bson.objectid import ObjectId
import pandas as pd
import numpy as np

import utils
from indicators import *
import drawgraphs as dg

looptime = int(os.environ.get('analyst_refresh', 2))
local_time_zone = os.environ['TZ']

output_graphs=os.environ['GRAPHPATH']

# dict key exported  will be "m" + 00000key to be exportable in javascript and easilly sortable.
# 'offset' values are used as title in gui and as pandas DataFrame time offset here.
pdef = {
        24*60*30: { 'offset': "30d"},
        24*60*7 : { 'offset': "7d"},
        24 * 60 : { 'offset': "1D", 'indicators': ['RSI', 'Bollinger'] },
         6 * 60 : { 'offset': "6H" , 'indicators': ['RSI', 'Bollinger'] },
             60 : { 'offset': "1H" , 'indicators': ['RSI', 'Bollinger'] },
             30 : { 'offset': "30Min" , 'indicators': ['RSI', 'Bollinger'] },
             15 : { 'offset': "15Min" , 'indicators': ['RSI', 'Bollinger'] },
              5 : { 'offset': "5Min"  , 'indicators': ['RSI', 'Bollinger'] },
              1 : { 'offset': "1Min"  , 'indicators': ['RSI', 'Bollinger'] },
}           

# pperiods is for statis periods
pperiods = dict(("p{:0>5}".format(k), v) for (k, v) in pdef.items())
# mperiods contains the moving period data
mperiods = dict(("mob_{:0>5}".format(k), v) for (k, v) in pdef.items())

# -  -  init  -  -
mongo_client = MongoClient('mongodb://' + utils.mongosvr +":" + utils.mongoport + '/')
db = mongo_client[utils.database_name]
rds = utils.redis_connect()

pairs = utils.Pairs(os.environ['pairs'].split()) # or  ['BTC-EUR', 'ETH-EUR'] 
#pairs = utils.Pairs(['BTC-EUR', 'ETH-EUR']) 
print("Starting Analyst. Pairs: ", pairs.keys())
coll_last_id = {} # last mongo ObjectId, by pair
lastprice = {} # used for the ticker and the periodic changes
stats = {}
frame = pd.DataFrame()
dftickers = {}

def get_data(pair):
    """ get mongo's last data for this pair, returns a DataFrame """
    collection = pairs.mdbpair(pair)
    if coll_last_id.get(collection): 
        filter_id = {'_id': {'$gt': ObjectId(coll_last_id.get(collection,0)) }}
    else:
        filter_id = {}
    data = list(db[collection].find(filter_id, 
               {"_id": 1, "time": 1, "isodate": 1, "price" : 1, "size" : 1},
               sort=[('_id', DESCENDING)]))
    if not data:
        return None
    # format dates
    idx =  pd.DatetimeIndex([x['isodate'] for x in data])
    idx = idx.tz_localize(tz=tz.tzutc())
    idx = idx.tz_convert(tz=local_time_zone)
    frame = pd.DataFrame(data, index=idx)
    # remember the last object fetched
    coll_last_id[collection] = frame['_id'][0]
    return frame

def set_ohlc(stats, df, offset):
    """ returns ohlc values by fixed periods """
    tmp = df['price'].resample(offset).ohlc()
    tmp['vol'] = df['size'].resample(offset).sum()
    for f in tmp[tmp.index.isin(stats.index)].index:
        stats.loc[f]['low']   = min([stats.loc[f]['low'], tmp.loc[f]['low']])
        stats.loc[f]['high']  = max([stats.loc[f]['high'], tmp.loc[f]['high']])
        stats.loc[f]['close'] = tmp.loc[f]['close']
        stats.loc[f]['vol']   = stats.loc[f]['vol'] + tmp.loc[f]['vol']
        stats.loc[f]["oc"] = (stats.loc[f]['close'] - stats.loc[f]['open']) *100 / stats.loc[f]['open']
    stats = stats.append(tmp.loc[~tmp.index.isin(stats.index)])
    stats['close'].fillna(method='ffill', inplace=True)
    stats['high'].fillna(stats['close'], inplace=True)
    stats['low'].fillna(stats['close'], inplace=True)
    stats['open'].fillna(stats['close'], inplace=True)
    return stats

def set_mobile_stats(frame, offset):
    """ returns mobile ohlc values in a dict """
    df = frame[frame.index >= datetime.now() - pd.to_timedelta(offset)].sort_index()
    if len(df) < 1:
        print("No data. Skip set_mobile_stats")
        return None
    res = {}
    res['low'] = df['price'].min() 
    res['high'] = df['price'].max() 
    res['vol'] = df['size'].sum() 
    res['range'] = res['high'] - res['low']
    res['oc'] = (df['price'][-1] - df['price'][0]) * 100. / df['price'][0]
    return res

if __name__ == "__main__":
    for pair in pairs.keys():
        stats[pair] = {}
        for period in pperiods.keys():
            stats[pair][period] = pd.DataFrame()
            dftickers[pair] = pd.DataFrame()
    while (True) :
        # calculate for all pairs
        for pair in pairs.keys():
            frame = get_data(pair)
            dftickers[pair] = dftickers[pair].append(frame)
            if frame is None:
                continue
            # make stats
            for period , opts in pperiods.items():
                stats[pair][period] = set_ohlc(stats[pair][period], frame, opts['offset'])
                if 'indicators' in opts.keys():
                    for i in opts['indicators']:
                        if i == "RSI":
                            stats[pair][period]['RSI-14'] = rsi(stats[pair][period]['close'][-100:])
                            stats[pair][period]['RSI-7'] = rsi(stats[pair][period]['close'][-100:], 7)
                            script, div = dg.draw_rsi(stats[pair][period][['RSI-7', 'RSI-14']][-100:], pair + " RSI " + opts['offset'])
                            fp = open("{}/{}_{}_RSI.div".format(output_graphs, pair, period), "w")
                            fp.write(div)
                            fp.close()
                            fp = open("{}/{}_{}_RSI.script".format(output_graphs, pair, period), "w")
                            fp.write(script)
                            fp.close()
                        elif i == "Bollinger":
                            stats[pair][period]['MA'], stats[pair][period]['BBUp'], stats[pair][period]['BBLow'] = \
                                    bollinger(stats[pair][period]['close'][-100:])
                            script, div = dg.draw_maingraph(stats[pair][period][-100:], opts['offset'], opts['offset'])
                            fp = open("{}/{}_{}_main.div".format(output_graphs, pair, period), "w")
                            fp.write(div)
                            fp.close()
                            fp = open("{}/{}_{}_main.script".format(output_graphs, pair, period), "w")
                            fp.write(script)
                            fp.close()
                        script, div = dg.draw_vol(stats[pair][period][-100:], opts['offset'], opts['offset'])
                        fp = open("{}/{}_{}_vol.div".format(output_graphs, pair, period), "w")
                        fp.write(div)
                        fp.close()
                        fp = open("{}/{}_{}_vol.script".format(output_graphs, pair, period), "w")
                        fp.write(script)
                        fp.close()
            lastprice[pair] = frame['price'][0]
            # make stats for mobile period
            res = {}
            for period in reversed(sorted(mperiods.keys())):
                stats[pair][period] = set_mobile_stats(dftickers[pair], mperiods[period]['offset'])
                if stats[pair][period] is None:
                    continue
                res[period] = stats[pair][period]
                res[period]['title'] = mperiods[period]['offset']
            # PUBSUB
            for period, opts in pperiods.items():
                res[period] = stats[pair][period].iloc[-1].replace({np.nan:None}).to_dict()
                res[period]['title'] = opts['offset']
            res['ticker'] = { 'price': lastprice[pair], 'pair': pair, 'oc': float(stats[pair]['mob_01440']['oc'])}
            rds.publish('cb:mkt:tick:pubsub', json.dumps({"type": "update", "data": res}))
            # put ticker in redis 
            rdkey = "cb:mkt:tick:" + pair
            rds.set(rdkey, str(lastprice[pair]))
            #rds.expire(rdkey, looptime + 20)
            # last periods
            rds.set("cb:mkt:change:" + pair, json.dumps(res)) 
        # wait before next stats
        time.sleep(looptime)
