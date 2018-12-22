#!/usr/bin/python -u

import sys, time, os, datetime, signal
import json, logging, redis

import utils

waittime = 1
logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/simple_bot.log', level=logging.NOTSET)

rbs = "trader:rb" # redis hash containing running bot status
hbs = "trader:hb" # redis hash containing history of ended bot status
rds_to_cambista = "cambi:order" # redis queue for orders
rds_to_cambista_sim = "cambisim:order" # redis queue for sim (fake) orders

class SimpleBot(object):
    def __init__(self, bot, redis_connection):
        self.instructions = []
        self.rds = redis_connection
        self.name = bot['name']
        self.pid = os.getpid()
        self.uid = bot['uid']
        self.pair = bot['pair']
        self.sim_mode = bot.get('sim_mode')
        self.status = "running"
        if bot.get('sim_mode'):
            self.rds_cambista = rds_to_cambista_sim
        else:
            self.rds_cambista = rds_to_cambista
        self.start_date = datetime.datetime.now()
        self.instructions_loop = bot.get('instructions_loop')
        self.instructions_index = bot.get('instructions_index', 0)
        self.instructions_count = bot.get('instructions_count', 0)
        for instruction in bot['instructions']:
            if not "pair" in instruction:
                instruction['pair'] = self.pair
            self.instructions.append(BotInstruction(instruction))
        self.update_redis_bot()

    def to_dict(self):
        return {
            "name": self.name,
            "pid": self.pid,
            "uid": self.uid,
            "type": "simple",
            "pair": self.pair,
            "sim_mode": self.sim_mode,
            "start_date": self.start_date.isoformat(),
            "instructions_loop": self.instructions_loop,
            "instructions_index": self.instructions_index,
            "instructions_count": self.instructions_count,
            "instructions": [ i.to_dict() for i in self.instructions ]
            }

    def update_redis_bot(self):
        if ( self.status == "running"):
            channel = rbs
        else:
            channel = hbs
        self.rds.hdel(channel, self.uid)
        self.rds.hset(channel, self.uid, json.dumps(self.to_dict()))
        print "Bot updated, see ", rbs 

    def archive_instruction(self):
        hist = self.get_current_instruction()
        hist["execution_date"] = datetime.datetime.now().isoformat()
        self.rds.lpush("trader:hist:" + self.uid, json.dumps(hist))
        
    def next_instruction(self):
        self.archive_instruction()
        self.instructions_index += 1
        self.instructions_count += 1
        if (self.instructions_index >= len(self.instructions)):
            if (self.instructions_loop):
                self.instructions_index = 0
            else:
                return None
        self.update_redis_bot()
        return self.get_current_instruction()
    
    def get_current_instruction(self):
        instructions =  self.instructions[self.instructions_index].to_dict()    
        instructions['uid'] = self.uid
        return instructions

    def waiting_order_id(self):
        return self.instructions[self.instructions_index].wait_filled

    def order_filled(self, order_id):
        self.instructions[self.instructions_index].order_filled(order_id)
        self.update_redis_bot()

    def send_order(self):
        res = self.rds.lpush(self.rds_cambista, json.dumps(self.get_current_instruction()))
        # wait order_id
        msg = self.rds.brpop("trader:tobot:" + self.uid)[1]
        logging.info("Received:" + msg)
        msg = json.loads(msg)
        # exit if order is refused
        if ( msg['type'] == "refused"):
            logging.info("Bot {} ({}): Order refused, will halt.".format(self.name, self.uid[:8]))
            utils.flash("Bot {} ({}): Order refused, will halt.".format(self.name, self.uid[:8]), "danger", sync=False)
            rds.lpush("trader:action", json.dumps({'uid': self.uid, "type": "stop_bot"}))
            time.sleep(5) # let time to trader to stop me
            return None
        order_id = msg['order_id']
        self.instructions[self.instructions_index].order_waited(order_id)
        self.update_redis_bot()
        return order_id

    def cancel_order(self, order_id):
        logging.info("Cancelling " + order_id)
        # send cancel order before the others with rpush
        self.rds.rpush(self.rds_cambista, json.dumps( { 'type': "cancel_order", "order_id": order_id, 'uid': self.uid } ))
        self.rds.brpop("trader:tobot:order_cancelled:" + self.uid)

    def wait_order_filled(self):
        logging.info("Waiting for filled order...")
        rds.brpop("trader:order_filled:" + self.waiting_order_id())
        self.order_filled(self.waiting_order_id())

    def end(self, status="ended"):
        logging.info("Cancel all orders...")
        for i in self.instructions:
            if (i.status == "wait_filled"):
                self.cancel_order(i.wait_filled)
                i.cancel()
        self.status = status
        self.update_redis_bot()
        sys.exit(0)

class BotInstruction(object):
    def __init__(self, instruction):
        self.size = instruction['size']
        self.side = instruction['side']
        self.price = instruction['price']
        self.type = instruction['type']
        self.pair = instruction['pair']
        self.wait_filled = instruction.get('wait_filled')
        self.start_date = instruction.get("start_date")
        self.status = instruction.get('status') # "wait_filled"|"cancelled"|None

    def to_dict(self):
        if self.start_date:
            start_date = self.start_date.isoformat()
        else:
            start_date = None
        return { "size": self.size, "side": self.side,
                "price": self.price, "type": self.type,
                "pair": self.pair, "wait_filled": self.wait_filled,
                "start_date": start_date, "status": self.status}

    def order_waited(self,order_id):
        self.start_date = datetime.datetime.now()
        self.status = "wait_filled"
        self.wait_filled = order_id

    def order_filled(self,order_id):
        self.status = None
        self.wait_filled = None

    def cancel(self):
        self.status = "cancelled"


# --- functions ---
def on_sigterm(signum, frame):
    mybot.end(status="cancelled") 
    logging.info("SIGTERM received")

# -----------------------------------------------
# -- init --
signal.signal(signal.SIGTERM, on_sigterm)

uid = sys.argv[1]
logging.info("%s Spawning Simplebot" % uid)

rds = utils.redis_connect()

botdata = json.loads(rds.get("trader:startbot:" + uid))
mybot = SimpleBot(botdata, redis_connection=rds)
rds.delete("trader:startbot:" + uid)

utils.flash("bot '{}' initialized (uid: {}, PID: {}".format(mybot.name, mybot.uid, mybot.pid), "success", sync=False)

while (True):
    if (mybot.get_current_instruction() is None):
        mybot.end()
    # could start by waiting if we're a reloaded bot
    if not mybot.waiting_order_id():
        mybot.send_order()

    mybot.wait_order_filled()
    mybot.next_instruction()

