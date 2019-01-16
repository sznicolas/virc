# Utils v 1.1

import redis, json, uuid

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
    """ send message to flask for 15sec AND to sse """
    """ Will be replaced by virc_publish           """
    fmessage = json.dumps( {
        "type": level,
        "data": message })
    msgkey = "gui:message:" + str(uuid.uuid4())[:8]
    rds.set(msgkey, fmessage)
    rds.expire(msgkey, 15)
    rds.publish("gui:flash", fmessage)

def virc_publish(message, category, level='info'):
    """ send message to flask in sync mode, or to sse """
    fmessage = json.dumps( {
        "type": "message",
        "data": {
            'message': message,
            'category': category,
            'level': level }
        } )
    rds.publish("virc:pubsub", fmessage)
    print "*** DBG virc_publish: %s" % fmessage

class Pairs():
    """ pairs exchanged we want to get are defined in docker-compose.yml 
    a conversion is needed since mongodb collections are in lowercase, without dash sign - """
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
