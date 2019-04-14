#!/usr/bin/env python

import sys, time, json, logging, os, requests
import redis, cbpro
import utils

looptime = 30 # in seconds. Must never be higher than 60sec (disconnects ws)

pairs = os.environ['pairs'].split()
cb_rw_keys = "coinbase-rw.json"
cb_ro_keys = "coinbase.json"
# conf
cambista_channel = os.environ.get("cambista_base_channel")
c_tobot = "trader:tobot"
channels = {'in'            : cambista_channel + ":orders",
            'error'         : cambista_channel + ":error",
            'order_done'    : c_tobot   + ":order_done:",
            'new_order'     : c_tobot   + ":new_order:",
            'order_status'  : c_tobot   + ":order_status:",
            'cancel_order'  : c_tobot   + ":cancel_order:"
            }
cambista_role = "real"
cambista_name = "Coinbase Pro"
cambista_icon = "fas fa-landmark"
cambista = utils.Cambista(
        {
            "role": cambista_role,
            "name": cambista_name,
            "icon": cambista_icon,
            "channels": channels
        }
)

def set_quote_increment(wsc, pairs):
    quote_increments = {}
    for l in wsc.get_products():
        if l['id'] in pairs:
            quote_increments[l['id']] = l['quote_increment'][::-1].find('.')
    return quote_increments

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
        msg = signmsg(msg)
        if ( msg['type'] == "error"):
            print "Error: ", msg
            logging.error(msg)
            rds.lpush("cb:wsuser:error" , msg)
        elif ( msg["type"] == "subscriptions" ):
            logging.info("Subscriptions : " + str(msg))
            return
        elif msg['type'] == "done":
            print msg
            recv = cb_get_order(msg['order_id'])
            msg['fees'] = recv['fill_fees']
            rds.lpush(channels["order_done"] + msg['order_id'], json.dumps(msg))
            logging.info("Order done. Reason: {} order_id: {}".format(msg['reason'], msg['order_id']))
            utils.flash("Order done. Reason: {} order_id: {}".format(msg['reason'], msg['order_id']), "info", sync=False)
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
                              price=round(msg['price'], quote_increments[msg['pair']]),
                              post_only=msg.get("post_only", True),
                              size=msg['size'])
    print recv
    return recv

def cb_sell(msg):
    recv = auth_client.place_limit_order(product_id=msg['pair'],
                              side='sell',
                              price=round(msg['price'], quote_increments[msg['pair']]),
                              post_only=msg.get("post_only", True),
                              size=msg['size'])
    print recv
    return recv

def cb_get_order(order_id):
    recv = auth_client.get_order(order_id)
    return recv

def cb_cancel_order(order_id):
    recv = auth_client.cancel_order(order_id)
    logging.info("Order canceled, received from server: %s " % recv)
    return { 'type': 'order_canceled', 'id': order_id}

def cb_send_order(order_msg):
    """ sends the order to cb's API, with retries. If unreachable, republish the received message to itself """
    auth_client = rw_auth()
    try:
        # Send buy/sell order
        if (order_msg['type'] == "order"):
            if ( order_msg['side'] == "buy"):
                recv = cb_buy(order_msg)
                logging.info("Buy order sent. recv = %s" % recv)
            elif ( order_msg['side'] == 'sell'):
                recv = cb_sell(order_msg)
                logging.info("Sell order sent. recv = %s" % recv)
            channel = channels['new_order'] + order_msg['uid']
        # Send cancel order:
        elif ( order_msg['type'] == 'cancel_order'):
            logging.info("Cancel Order '%s'" % order_msg['order_id']) 
            recv = cb_cancel_order(order_msg['order_id'])
            channel = channels['cancel_order'] + order_msg['uid']
        # get order status
        elif ( order_msg['type'] == 'get_order_status'):
            recv = cb_get_order(order_msg['order_id'])
            channel = channels['order_status'] + order_msg['order_id']
        # Unknown message
        else:
          logging.warning("Message type unknown in " + str(recv))
    except requests.exceptions.ReadTimeout:
        order_msg = signmsg(order_msg)
        logging.error("ReadTimeout ! Re-register message '%s'" % order_msg)
        utils.flash("ReadTimeout ! Re-register message '%s'" % json.dumps(order_msg), "danger", sync=False)
        if ("send_retries" in order_msg.keys()):
            order_msg['send_retries'] += 1
        else:
            order_msg['send_retries'] = 1
        rds.lpush(channels['in'], json.dumps(order_msg))
        return 

    recv = signmsg(recv)
    # if order is refused:
    if ("message" in recv.keys()):
        recv["type"] = "refused"
        rds.lpush(channels['error'], json.dumps(recv))
        utils.flash("Order refused ; '%s'" % json.dumps(recv), "danger", sync=False)
        logging.error("Order refused ; '%s'" % json.dumps(recv))
    if 'id' in recv.keys(): # in some case cb api names 'id' the 'order_id'
        recv['order_id'] = recv.get('id')
    rds.lpush(channel, json.dumps(recv))
    logging.info("pushed '{}' to '{}'".format(recv, channel))


def signmsg(msg):
    msg['cambista_name'] = cambista_name
    msg['cambista_channel'] = cambista_channel
    return msg

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

quote_increments = set_quote_increment(auth_client, pairs)
wsClient.start()
logging.info("Cambista is ready")

# set cambista info
regkey = os.environ.get("CAMBISTA_CHANNELS") + cambista_channel
rds.set(regkey, json.dumps(cambista.to_dict()))

while (True):
    # Workaround disconnect after 60sec of inactivity:
    if wsClient.ws:
        wsClient.ws.ping("keepalive")

    # declare myself as running
    rds.expire(regkey, 60)

    # get new message
    rdsmsg = rds.brpop(channels['in'], looptime)
    if (rdsmsg is not None):
        logging.info("Cambista received: %s" % str(rdsmsg))
        try:
            order_msg = json.loads(rdsmsg[1])
            order_msg = signmsg(order_msg)
            # pre check data
            order_msg['uid'], order_msg['type']
        except:
            logging.error("Message is not well formatted. Pushed to " + cambista_channel + ":error")
            rds.lpush(channels['error'], str(rdsmsg))
            continue
        cb_send_order(order_msg)

logging.info("End")
wsClient.close()

