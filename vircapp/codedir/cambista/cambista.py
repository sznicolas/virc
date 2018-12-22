#!/usr/bin/env python

import sys, time, json, logging, os, requests
import redis, cbpro
import utils

looptime = 30 # in seconds. Must never be higher than 60sec (disconnects ws)

pairs = os.environ['pairs'].split()
cb_rw_keys = "coinbase-rw.json"
cb_ro_keys = "coinbase.json"

def rw_auth():
    creds_rw = json.loads(open(cb_rw_keys).read())
    c = cbpro.AuthenticatedClient(creds_rw["key"], creds_rw["api_secret"], creds_rw['passphrase'])
    return c

def ro_auth():
    creds = json.loads(open(cb_ro_keys).read())
    wsClient = myWebsocketClient(auth=True, api_key=creds["key"], \
        api_secret=creds["api_secret"], api_passphrase=creds["passphrase"])
    return wsClient

class myWebsocketClient(cbpro.WebsocketClient):
    def on_open(self):
        self.url = "wss://ws-feed.pro.coinbase.com/"
        self.products = pairs
        self.channels = ["user"]
        self.message_count = 0
        self.encountered_types = []

    def on_message(self, msg):
        self.message_count += 1
        logging.info("ws received:" + str(msg))
        if ( msg['type'] == "error"):
            print "Error: ", msg
            logging.error(msg)
            rds.lpush("cb:wsuser:error" , msg)
        elif ( msg["type"] == "subscriptions" ):
            logging.info("Subscriptions : " + str(msg))
            return
        elif (msg['type'] == "done" and msg['reason'] == "filled"):
            print msg
            rds.lpush("trader:order_filled:" + msg['order_id'], json.dumps(msg))
            logging.info("Filled: " + msg['order_id'])
            utils.flash("Order '%s' filled" % msg['order_id'], "info", sync=False)
        if (not  msg["type"] in self.encountered_types ):
            print (json.dumps(msg, indent=4, sort_keys=True))
            self.encountered_types.append(msg["type"])

    def on_close(self):
        logging.info("on_close: Websocket closed")
        logging.info("Received : {} message(s)".format(self.message_count))
        sys.exit(4)

def cb_buy(msg):
    recv = auth_client.place_limit_order(product_id=msg['pair'],
                              side='buy',
                              price=msg['price'],
                              post_only=msg.get("post_only", True),
                              size=msg['size'])
    print recv
    return recv

def cb_sell(msg):
    recv = auth_client.place_limit_order(product_id=msg['pair'],
                              side='sell',
                              price=msg['price'],
                              post_only=msg.get("post_only", True),
                              size=msg['size'])
    print recv
    return recv

def cb_cancel_order(order_id):
    recv = auth_client.cancel_order(order_id)
    print "Cancelled, recv =\n%s" %recv
    return recv


def cb_send_order(order_msg):
    try:
        if (order_msg['type'] == "order"):
            # send order
            if ( order_msg['side'] == "buy"):
                recv = cb_buy(order_msg)
                logging.info("Buy order sent. recv = %s" % recv)
            elif ( order_msg['side'] == 'sell'):
                recv = cb_sell(order_msg)
                logging.info("Sell order sent. recv = %s" % recv)
        # send cancel order:
        elif ( order_msg['type'] == 'cancel_order'):
            logging.info("Cancel Order '%s'" % order_msg['order_id']) 
            recv = cb_cancel_order(order_msg['order_id'])
            rds.lpush("trader:tobot:order_cancelled:" + order_msg['uid'], json.dumps({ 'type': 'order_cancelled', 'order_id': order_msg['order_id']}))
        else:
          logging.warning("Message type unknown in " + str(recv))
    except requests.exceptions.ReadTimeout:
        logging.error("ReadTimeout ! Re-register message '%s'" % order_msg)
        utils.flash("ReadTimeout ! Re-register message '%s'" % json.dumps(order_msg), "danger", sync=False)
        print "ReadTimeout ! Re-register message '%s'" % order_msg
        if ("send_retries" in order_msg.keys()):
            order_msg['send_retries'] += 1
        else:
            order_msg['send_retries'] = 1
        rds.lpush("cambi:order", json.dumps(order_msg))
        return 
    # if order is refused:
    if ("message" in recv.keys()):
        recv["type"] = "refused"
        rds.lpush("cambista:error", json.dumps(recv))
        rds.lpush("trader:tobot:" + order_msg['uid'] , json.dumps(recv))
        utils.flash("Order refused ; '%s'" % json.dumps(recv), "danger", sync=False)
    # order accepted, send order_id to bot:
    else:
        recv['order_id'] = recv['id'] # in this case cb api calls it 'id'
        rds.lpush("trader:tobot:" + order_msg['uid'], json.dumps(recv))
        logging.info("push to 'trader:tobot': %s" % recv)


# -----------------------------------------------
# -- init --
# logging
logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/cambista.log', level=logging.NOTSET)

rds = utils.redis_connect()

# coinbase connections
try:    
    auth_client = rw_auth()
    wsClient = ro_auth()
except Exception as e:
    errmsg = "Cambista can't be started. Reason: '%s'. Please verify your json key files %s and %s" % (e, cb_ro_keys, cb_rw_keys)
    print errmsg 
    utils.flash(errmsg, 'danger')
    logging.error(errmsg)
    #sys.exit(78)
    sys.exit(0) # not restarted by docker-compose

wsClient.start()
logging.info("Cambista is ready")


count = 5
while (True):
    # Workaround disconnect after 60sec of inactivity:
    if wsClient.ws:
        wsClient.ws.ping("keepalive")

    # get new message
    rdsmsg = rds.brpop("cambi:order", looptime)
    if (rdsmsg is not None):
        logging.info("Cambista received: %s" % str(rdsmsg))
        try:
            order_msg = json.loads(rdsmsg[1])
            # pre check data
            order_msg['uid'], order_msg['type']
        except:
            logging.error("Message is not well formatted. Pushed to cambi:error")
            rds.lpush("cambi:error", str(rdsmsg))
            continue
        cb_send_order(order_msg)

logging.info("End")
wsClient.close()

""" messages
{u'user_id': u'cccccccccccccccccccccccc', u'product_id': u'BTC-EUR', u'sequence': 4665914249, u'taker_order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'profile_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'price': u'5644.50000000', u'trade_id': 16459221, u'maker_user_id': u'cccccccccccccccccccccccc', u'time': u'2018-10-25T14:31:57.526000Z', u'maker_order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'maker_profile_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'type': u'match', u'side': u'buy', u'size': u'0.05000000'}
{
    "maker_order_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "maker_profile_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "maker_user_id": "cccccccccccccccccccccccc", 
    "price": "5644.50000000", 
    "product_id": "BTC-EUR", 
    "profile_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "sequence": 4665914249, 
    "side": "buy", 
    "size": "0.05000000", 
    "taker_order_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "time": "2018-10-25T14:31:57.526000Z", 
    "trade_id": 16459221, 
    "type": "match", 
    "user_id": "cccccccccccccccccccccccc"
}
{u'user_id': u'cccccccccccccccccccccccc', u'product_id': u'BTC-EUR', u'remaining_size': u'0', u'sequence': 4665914250, u'order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'price': u'5644.50000000', u'profile_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'reason': u'filled', u'time': u'2018-10-25T14:31:57.526000Z', u'type': u'done', u'side': u'buy'}
{
    "order_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "price": "5644.50000000", 
    "product_id": "BTC-EUR", 
    "profile_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "reason": "filled", 
    "remaining_size": "0", 
    "sequence": 4665914250, 
    "side": "buy", 
    "time": "2018-10-25T14:31:57.526000Z", 
    "type": "done", 
    "user_id": "cccccccccccccccccccccccc"
}



{u'client_oid': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'user_id': u'cccccccccccccccccccccccc', u'order_type': u'limit', u'sequence': 4665948365, u'order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'price': u'5666.64000000', u'profile_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'product_id': u'BTC-EUR', u'time': u'2018-10-25T14:38:45.282000Z', u'type': u'received', u'side': u'sell', u'size': u'0.05000000'}
{
    "client_oid": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "order_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "order_type": "limit", 
    "price": "5666.64000000", 
    "product_id": "BTC-EUR", 
    "profile_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "sequence": 4665948365, 
    "side": "sell", 
    "size": "0.05000000", 
    "time": "2018-10-25T14:38:45.282000Z", 
    "type": "received", 
    "user_id": "cccccccccccccccccccccccc"
}
{u'user_id': u'cccccccccccccccccccccccc', u'product_id': u'BTC-EUR', u'remaining_size': u'0.05000000', u'sequence': 4665948366, u'order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'price': u'5666.64000000', u'profile_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'time': u'2018-10-25T14:38:45.282000Z', u'type': u'open', u'side': u'sell'}
{
    "order_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "price": "5666.64000000", 
    "product_id": "BTC-EUR", 
    "profile_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", 
    "remaining_size": "0.05000000", 
    "sequence": 4665948366, 
    "side": "sell", 
    "time": "2018-10-25T14:38:45.282000Z", 
    "type": "open", 
    "user_id": "cccccccccccccccccccccccc"
}
"""
