# Utils v 1.0

import redis
import json

redissrv = "redis"
redisport = 6379
mongosvr = "mongo"
mongoport = "27017"
database_name = "cryptomarket_db"
__pairs__ = {}
rds = None

def redis_connect():
    global rds 
    global __pairs__
    rds = redis.StrictRedis(host=redissrv, port=redisport, db=0)
    try:
        rds.ping()
        __pairs__ = json.loads(rds.get("virc:convproducts"))
    except redis.exceptions.ConnectionError as ce:
        print "No redis connection to {}:{}".format(redissrv, redisport)
        raise 
    return rds

def pairconvert(pair):
  return __pairs__.get(pair)

def flash(message, level="info", sync=True):
    """ send message to flask in sync mode, or to sse """
    print "utils.flash. type: {} - content: {}".format(type(message), message)
    fmessage = json.dumps( {
        "type": level,
        "data": message })
    if sync:
        rds.lpush("gui:message", fmessage)
    else:
        rds.publish("gui:flash", fmessage)
    print "utils.flash. fmessage type: {} - content: {}".format(type(fmessage), fmessage)

if __name__ == "__main__":
    pass
