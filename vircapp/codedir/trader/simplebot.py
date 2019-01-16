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
        mybot.end("canceled")
    stop_bot(mybot, bcancel_orders=True, alert_trader=False)

def stop_bot(bot, bcancel_orders=False, status=None, exitcode=0, alert_trader=True):
    if (bcancel_orders):
        cancel_order(bot)
    if (status):
        bot.end(status=status) 
    if (alert_trader):
        # error on server side if it's in brpop
        rds.lpush("trader:action", json.dumps({'uid': bot.uid, "type": "stop_bot"}))
    update_blueprint(bot)
    utils.flash("bot '{}' is stopping. Status: {}".format(bot.name, bot.status), "info", sync=False)
    sys.exit(exitcode)

def update_blueprint(bot):
    if ( bot.get_status() == "running"):
        channel = rbs + ":" + bot.uid
    else:
        channel = hbs + ":" + bot.uid
        rds.delete(rbs + ":" + bot.uid)
    rds.delete(channel)
    rds.set(channel, json.dumps(bot.to_dict()))
    print "Bot '%s' updated, see %s" % (bot.name, channel)

def send_order(bot):
    res = rds.lpush(cambista_defs['channels']['in'], json.dumps(bot.get_current_instruction()))
    # wait order_id
    msg = rds.brpop(cambista_defs['channels']['new_order'] + bot.uid)
    logging.info("Received:" + str(msg))
    msg = json.loads(msg[1])
    if ( msg['type'] == "refused"):
        logging.info("Bot {} ({}): Order refused. Reason: {}".format(bot.name, bot.uid[:8], msg))
        utils.flash("Bot '{}': Order refused. Reason: {}".format(bot.name, msg), "danger", sync=False)
        return None
    order_id = msg['order_id']
    return order_id

def cancel_order(bot):
    logging.info("Cancelling " + bot.current_instruction.get_order_id())
    # send cancel order before the others with rpush
    rds.rpush(cambista_defs['channels']['in'], json.dumps( { 'type': "cancel_order",
                "order_id": bot.current_instruction.get_order_id(), 'uid': bot.uid } ))
    rds.brpop(cambista_defs['channels']['cancel_order'] + bot.uid)[1]
    bot.current_instruction.cancel()


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

utils.flash("bot '{}' initialized".format(mybot.name), "success", sync=False)

for instruction in mybot.iter_instructions():
    # If we have a reloaded bot we've already an order sent
    waited_order_id = mybot.current_instruction.get_order_id()
    if waited_order_id is None:
        waited_order_id = send_order(mybot)
        if (waited_order_id is None):
            stop_bot(mybot, status="order refused", exitcode=4)
        mybot.current_instruction.set_order_id(waited_order_id)
        update_blueprint(mybot)
    else:
        print ("Reloaded bot, verify previously sent order")
        logging.info("Reloaded bot, verify previously sent order")
        rds.lpush(cambista_defs['channels']['in'], 
                json.dumps({'type' : 'get_order_status', 'order_id': waited_order_id, 'uid': mybot.uid}))
        msg = json.loads(rds.brpop(cambista_defs['channels']['order_status'] +  waited_order_id)[1])
        print "*** ", msg
        if (msg.get('status') != "open"):
            # TODO: what if filled ?
            utils.flash("Order is not in 'open' state, exit.")
            logging.info("Order is not in 'open' state, exit.")
            stop_bot(mybot, status="order not open", exitcode=4)
        

    logging.info("Waiting for order %s execution..." % waited_order_id)
    msg = rds.brpop(cambista_defs['channels']['order_done'] + waited_order_id)[1]
    print "Sb:" , msg
    msg = json.loads(msg)
    if (msg['reason'] == "canceled"):
        utils.flash("Order canceled by user, exit")
        stop_bot(mybot, status="order canceled by user")
        sys.exit(10)
    elif (msg['reason'] == "filled"):
        mybot.current_instruction.set_order_filled(waited_order_id)
    else:
        utils.flash("Unknown reason, exit")
        stop_bot(mybot, status="Unknown reason")
        logging.error("Msg received: '%s'" % (msg))
        sys.exit(11)

    logging.info("Order %s is filled." % (waited_order_id))
    update_blueprint(mybot)

stop_bot(mybot, status="ended")
update_blueprint(mybot)
