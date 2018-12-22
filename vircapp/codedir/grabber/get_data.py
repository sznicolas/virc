#!/usr/bin/env python

# virc get_data
# get trades and write them in the mongodb collection
#
# TODO:
# get the pairs in env variable defined in docker-compose
#
import cbpro
import os, time, json
import dateutil.parser
from pymongo import MongoClient, ASCENDING, DESCENDING

# pairs exchanged we want to get are defined in docker-compose.yml
pairs = os.environ['pairs'].split() # or  ['BTC-EUR', 'ETH-EUR'] 
# mongodb pairs, lowercase and without dash -
mdbpair = dict( (map(lambda x: (x, x.lower().replace("-", "")) , pairs)))

redissrv = "redis"
redisport = 6379
mongosvr = "mongo"
mongoport = "27017"

looptime = 30 # in seconds. Must never be higher than 60sec (can be disconnected by timeout)

class myWebsocketClient(cbpro.WebsocketClient):
    def on_open(self):
        self.url = "wss://ws-feed.pro.coinbase.com/"
        self.products = pairs
        self.channels = ["matches"] #, "heartbeat"]
        self.message_count = 0
        self.encountered_types = []

    def on_message(self, msg):
        self.message_count += 1
        if ( msg["type"] == "subscriptions" ):
            print ("Subscriptions : ", msg)
            return
        if (not  msg["type"] in self.encountered_types ):
            print (json.dumps(msg, indent=4, sort_keys=True))
            self.encountered_types.append(msg["type"])
        if (msg['type'] == "match" and 'time' in msg):
            # convert data
            msg['isodate'] = dateutil.parser.parse(msg['time'])
            for f in [ "price", "size"]:
                msg[f] = float(msg[f])
            collection = db[mdbpair[msg['product_id']]]
            collection.insert_one(msg)
     #   elif (msg['type'] == "heartbeat"):

        else:
            print("-----------------")
            print (msg)
            print("=---------------=")

    def on_close(self):
        print("{} : on_close: Websocket unexpectedly closed").format(str(time.ctime(int(time.time()))))
        print("Received : {} message(s)".format(self.message_count))


# -----------------------------------------------
# -- init --

print "Connecting to the services..."

mongo_client = MongoClient('mongodb://' + mongosvr +":" + mongoport + '/')
db = mongo_client.cryptomarket_db
for k in mdbpair: 
    collection = db[mdbpair[k]]
    collection.create_index([("isodate", ASCENDING)], name="isodate", unique=False)

wsClient = myWebsocketClient()

wsClient.start()
print("{} : Ready").format(str(time.ctime(int(time.time()))))

# Workaround disconnect after 60sec of inactivity:
while (True):
    if wsClient.ws:
        wsClient.ws.ping("keepalive")
    time.sleep(looptime)
