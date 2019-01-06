#!/usr/bin/python -u

import sys, time, datetime, signal
import json, logging, redis

import utils
import bot

logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/simple_bot.log', level=logging.NOTSET)

rbs = "trader:rb" # redis hash containing running bot status
hbs = "trader:hb" # redis hash containing history of ended bot status

# --- functions ---
def on_sigterm(signum, frame):
    """ trader.py sends SIGTERM to stop the bot then wait() """
    logging.info("received SIGTERM, will cancel orders and halt.")
    if (mybot.get_status() == "running") :
        mybot.end("cancelled")
    stop_bot(mybot, cancel_orders=True)

def stop_bot(bot, cancel_orders=False, status=None, exitcode=0, alert_trader=True):
    if (cancel_orders):
        cancel_orders(mybot)
    if (status):
        mybot.end(status=status) 
    if (alert_trader):
        rds.lpush("trader:action", json.dumps({'uid': mybot.uid, "type": "stop_bot"}))
    update_blueprint(mybot)
    sys.exit(exitcode)

def update_blueprint(bot):
    if ( bot.get_status() == "running"):
        channel = rbs
    else:
        channel = hbs
    rds.hdel(channel, bot.uid)
    rds.hset(channel, bot.uid, json.dumps(bot.to_dict()))
    print "Bot updated, see ", channel

def send_order(bot):
    res = rds.lpush(cambista_defs['channels']['in'], json.dumps(bot.get_current_instruction()))
    # wait order_id
    msg = rds.brpop(cambista_defs['channels']['new_order'] + bot.uid)[1]
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
    rds.rpush(cambista_defs['channels']['in'], json.dumps( { 'type': "cancel_order",
                "order_id": order_id, 'uid': bot.uid } ))
    rds.brpop(cambista_defs['channels']['cancel_order'] + bot.uid)


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
# get cambista channels
cambista_defs = json.loads(rds.get(mybot.get_cambista_link()))
rds.delete("trader:startbot:" + uid)
update_blueprint(mybot)

utils.flash("bot '{}' initialized (uid: {}, PID: {}".format(mybot.name, mybot.uid, mybot.pid), "success", sync=False)

while (True):
    # could start by waiting if we have a reloaded bot
    waited_order_id = mybot.get_waited_order_id()
    if waited_order_id is None:
        waited_order_id = send_order(mybot)
        if (waited_order_id is None):
            stop_bot(mybot, status="order refused", exitcode=4)
        mybot.set_current_instruction_wait_order(waited_order_id)
        update_blueprint(mybot)
    else:
        logging.info("Reloaded bot, instruction previously sent")

    logging.info("Waiting for order %s execution..." % waited_order_id)
    rds.brpop(cambista_defs['channels']['order_filled'] + waited_order_id)
    logging.info("Order %s is filled." % waited_order_id)
    mybot.set_order_filled(waited_order_id)

    archive_instruction(mybot)
    if (mybot.next_instruction() is None):
        stop_bot(mybot, status="ended")
    update_blueprint(mybot)

