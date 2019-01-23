#!/usr/bin/python -u

import sys, time, datetime, signal
import json, logging, redis

import utils
import bot

logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/simple_bot.log', level=logging.NOTSET)

# --- functions ---
def on_sigterm(signum, frame):
    """ trader.py sends SIGTERM to stop the bot then wait() 
        SIGUSR1 can be used to set the bot in pause mode. 
          In  this case the only change is that the current order
          is not canceled, and the status is set to 'paused'    
    """
    if signum == signal.SIGUSR1 :
        logging.info("received SIGUSR1, will halt.")
        if (mybot.get_status() == "running") :
            mybot.end("paused")
        stop_bot(mybot, bcancel_orders=False, status="paused", alert_trader=False)

    elif signum == signal.SIGTERM:
        logging.info("received SIGTERM, will cancel orders and halt.")
        if (mybot.get_status() == "running") :
            mybot.end("canceled")
        stop_bot(mybot, bcancel_orders=True, alert_trader=False)

def stop_bot(bot, bcancel_orders=False, status=None, exitcode=0, alert_trader=True):
    if (bcancel_orders):
        logging.info("Cancelling " + bot.get_order_id())
        bot.cancel_order()
    if (status):
        bot.end(status=status) 
    if (alert_trader):
        # error on server side if it's in brpop
        rds.lpush("trader:action", json.dumps({'uid': bot.uid, "type": "stop_bot"}))
    bot.update_blueprint()
    utils.flash("bot '{}' is stopping. Status: {}".format(bot.name, bot.status), "info", sync=False)
    sys.exit(exitcode)



# -----------------------------------------------
# -- init --
signal.signal(signal.SIGTERM, on_sigterm)
signal.signal(signal.SIGUSR1, on_sigterm)
rds = utils.redis_connect()

uid = sys.argv[1]
logging.info("%s Spawning Simplebot" % uid)
try:
    botdata = json.loads(rds.get("trader:startbot:" + uid))
except Exception as e:
    logging.error("Error '{}': no data in redis's 'trader:startbot:{}'".format(e, uid))
    sys.exit(9)

#mybot = bot.SimpleBot(botdata)
mybot = bot.OrderBot(botdata, rds)
rds.delete("trader:startbot:" + uid)
mybot.update_blueprint()

utils.flash("bot '{}' initialized".format(mybot.name), "success", sync=False)

for instruction in mybot.iter_instructions():
    waited_order_id = mybot.get_order_id()
    if waited_order_id is None:
        # send new order to Cambista
        waited_order_id = mybot.send_order()
        if (waited_order_id is None):
            logging.info("Bot {} ({}): Order refused. Reason: {}".format(mybot.name, mybot.uid[:8], mybot.error))
            utils.flash("Bot '{}': Order refused. Reason: {}".format(mybot.name, mybot.error), "danger", sync=False)
            stop_bot(mybot, status="order refused", exitcode=4)
        mybot.set_order_id(waited_order_id)
        mybot.update_blueprint()
    else:
    # If we have a reloaded bot we've already an order sent
        msg = mybot.get_order_status()
        if (msg.get('status') == "filled"):
            mybot.set_order_filled(waited_order_id)
            logging.info("{}: Order {} is filled.".format(mybot.name, waited_order_id))
            utils.flash("{}: Order {} is filled.".format(mybot.name, waited_order_id))
            mybot.update_blueprint()
            continue
        elif (msg.get('status') != "open"):
            utils.flash("Order is not in 'open' state, exit.")
            logging.info("Order is not in 'open' state, exit.")
            stop_bot(mybot, status="order not open", exitcode=4)
    # wait for order filled or canceled
    logging.info("Waiting for order %s execution..." % waited_order_id)
    msg = mybot.wait_order_update()
    if (msg['reason'] == "canceled"):
        utils.flash("Order canceled by user, exit")
        stop_bot(mybot, status="order canceled by user")
        sys.exit(10)
    elif (msg['reason'] == "filled"):
        mybot.set_order_filled(waited_order_id)
    else:
        utils.flash("Unknown reason, exit")
        stop_bot(mybot, status="Unknown reason")
        logging.error("Msg received: '%s'" % (msg))
        sys.exit(11)

    logging.info("Order %s is filled." % (waited_order_id))
    mybot.update_blueprint()

stop_bot(mybot, status="ended")
mybot.update_blueprint()
