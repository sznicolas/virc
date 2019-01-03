#!/usr/bin/python -u

import sys, time, datetime, signal
import json, logging, redis

import utils
import bot

logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/simple_bot.log', level=logging.NOTSET)

rbs = "trader:rb" # redis hash containing running bot status
hbs = "trader:hb" # redis hash containing history of ended bot status
rds_to_cambista = "cambista:cb:orders" # redis queue for orders
rds_to_cambista_sim = "cambista:sim:orders" # redis queue for sim (fake) orders

# --- functions ---
def on_sigterm(signum, frame):
    """ trader.py sends SIGTERM to stop the bot then wait() """
    logging.info("received SIGTERM, will cancel orders and halt.")
    cancel_orders(mybot)
    mybot.end(status="cancelled") 
    update_blueprint(mybot)
    sys.exit(0)

def update_blueprint(bot):
    if ( bot.get_status() == "running"):
        channel = rbs
    else:
        channel = hbs
    rds.hdel(channel, bot.uid)
    rds.hset(channel, bot.uid, json.dumps(bot.to_dict()))
    print "Bot updated, see ", channel

def send_order(bot):
    res = rds.lpush(rds_cambista, json.dumps(bot.get_current_instruction()))
    # wait order_id
    msg = rds.brpop("trader:tobot:new_order:" + bot.uid)[1]
    logging.info("Received:" + msg)
    msg = json.loads(msg)
    if ( msg['type'] == "refused"):
        logging.info("Bot {} ({}): Order refused. Reason: {}".format(bot.name, bot.uid[:8], msg))
        utils.flash("Bot '{}': Order refused. Reason: {}".format(bot.name, msg), "danger", sync=False)
        return None
    order_id = msg['order_id']
    return order_id

def cancel_order(bot, order_id):
    logging.info("Cancelling " + order_id)
    # send cancel order before the others with rpush
    rds.rpush(rds_cambista, json.dumps( { 'type': "cancel_order",
                "order_id": order_id, 'uid': bot.uid } ))
    rds.brpop("trader:tobot:cancel_order:" + bot.uid)


def cancel_orders(bot):
    for i in bot.get_instructions():
        if (i.status == "wait_filled"):
            cancel_order(bot, i.get_wait_order_id())
            i.cancel()

def archive_instruction(bot):
    hist = bot.get_current_instruction()
    hist["execution_date"] = datetime.datetime.now().isoformat()
    rds.lpush("trader:hist:" + bot.uid, json.dumps(hist))
        
# -----------------------------------------------
# -- init --
signal.signal(signal.SIGTERM, on_sigterm)
rds = utils.redis_connect()

uid = sys.argv[1]
logging.info("%s Spawning Simplebot" % uid)
try:
    botdata = json.loads(rds.get("trader:startbot:" + uid))
except Exception as e:
    logging.error("Error '{}': no data in redis's 'trader:startbot:{}'".format(e, uid))
    sys.exit(9)

mybot = bot.SimpleBot(botdata)
# where to send orders (sim|real)
if mybot.issim_mode():
    rds_cambista = rds_to_cambista_sim
else:
    rds_cambista = rds_to_cambista
rds.delete("trader:startbot:" + uid)
update_blueprint(mybot)

utils.flash("bot '{}' initialized (uid: {}, PID: {}".format(mybot.name, mybot.uid, mybot.pid), "success", sync=False)

while (True):
    if (mybot.get_current_instruction() is None):
        mybot.end()
        update_blueprint(mybot)
        sys.exit(0)

    # could start by waiting if we have a reloaded bot
    waited_order_id = mybot.get_waited_order_id()
    if waited_order_id is None:
        waited_order_id = send_order(mybot)
        if (waited_order_id is None):
            mybot.end(status="order refused")
            rds.lpush("trader:action", json.dumps({'uid': mybot.uid, "type": "stop_bot"}))
            time.sleep(5) # let time to trader to stop me
            sys.exit(4)
        mybot.set_current_instruction_wait_order(waited_order_id)
        update_blueprint(mybot)
    else:
        logging.info("Reloaded bot, instruction previously sent")

    logging.info("Waiting for order %s execution..." % waited_order_id)
    rds.brpop("trader:tobot:order_filled:" + waited_order_id)
    logging.info("Order %s is filled." % waited_order_id)
    mybot.set_order_filled(waited_order_id)

    archive_instruction(mybot)
    mybot.next_instruction()
    update_blueprint(mybot)

