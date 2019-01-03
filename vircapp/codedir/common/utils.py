# Utils v 1.0

import redis
import json

redissrv = "redis"
redisport = 6379
mongosvr = "mongo"
mongoport = "27017"
database_name = "cryptomarket_db"
rds = None

def redis_connect():
    global rds 
    global __pairs__
    rds = redis.StrictRedis(host=redissrv, port=redisport, db=0)
    try:
        rds.ping()
    except redis.exceptions.ConnectionError as ce:
        print "No redis connection to {}:{}".format(redissrv, redisport)
        raise 
    return rds

def flash(message, level="info", sync=True):
    """ send message to flask in sync mode, or to sse """
#    print "utils.flash. type: {} - content: {}".format(type(message), message)
    fmessage = json.dumps( {
        "type": level,
        "data": message })
    if sync:
        rds.lpush("gui:message", fmessage)
    else:
        rds.publish("gui:flash", fmessage)
#    print "utils.flash. fmessage type: {} - content: {}".format(type(fmessage), fmessage)

class Pairs():
    """ pairs exchanged we want to get are defined in docker-compose.yml """
    def __init__(self, pairs):
        self.pair = {}
        for p in pairs:
            self.pair[p] = p.lower().replace("-", "") 
        
    def mdbpair(self, pair):
        return self.pair[pair]

    def keys(self):
        return self.pair.keys()

    def values(self):
        return self.pair.values()

    def __getitem__(self, index):
        return self.pair[index]


if __name__ == "__main__":
    pass
