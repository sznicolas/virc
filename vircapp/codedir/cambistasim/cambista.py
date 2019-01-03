#!/usr/bin/env python

import sys, time, json, logging, uuid, datetime, os
import utils

looptime = 1 # in seconds.

# logging
logging.basicConfig(format='%(asctime)s %(message)s', filename='/logs/cambista_sim.log', level=logging.NOTSET)

# conf
c_camb = os.environ.get("cambista_base_channel")
c_tobot = "trader:tobot"
channels = {'in'            : c_camb + ":orders",
            'error'         : c_camb + ":error",
            'order_filled'  : c_tobot   + ":order_filled:",
            'new_order'     : c_tobot   + ":new_order:",
            'cancel_order'  : c_tobot   + ":cancel_order:"
            }
cambista_role = "sim"
cambista_platform = "Coinbase Emulated"

class OrderBook(object):
    def __init__(self, redis_connection):
        self.rds = redis_connection
        self.orders= []
        self._get_orders()

    def buy(self, msg):
        order_id = str(uuid.uuid4())
        self.add_order({
            'pair': msg['pair'], 'price': msg['price'],
            'size': msg['size'], 'order_id': order_id,
            'side': 'buy'
            })
        return order_id

    def sell(self, msg):
        order_id = str(uuid.uuid4())
        self.add_order({
            'pair': msg['pair'], 'price': msg['price'],
            'size': msg['size'], 'order_id': order_id,
        'side': 'sell'
        })
        return order_id

    def add_order(self, order):
        self.orders.append(order)
        self._set_orders()

    def del_order(self, index):
        self.orders.pop(index)
        self._set_orders()

    def cancel_order(self, order_id):
        index = self.find_order_by_id(order_id)
        if index is None:
            utils.flash("order '{}' not found. Can't be cancelled".format(order_id), "error", sync=false )
        else:
            self.del_order(index)

    def find_order_by_id(self, order_id):
        i = 0
        for o in self.orders:
            if o['order_id'] == order_id:
                return i
            i += 1
        return None

    def _get_orders(self):
        orders = self.rds.get("cambisim:orderbook")
        if (orders is not None):
            self.orders = json.loads(orders)
        else:
            self.orders = []

    def _set_orders(self):
        self.rds.set("cambisim:orderbook", json.dumps(self.orders))

# -----------------------------------------------
# -- init --
rds = utils.redis_connect()
logging.info("Started.")
orderbook = OrderBook(redis_connection=rds)

while (True):
    # declare myself as running
    regkey = os.environ.get("CAMBISTA_CHANNELS") + c_camb
    rds.set(regkey, json.dumps({"role": cambista_role, "platform": cambista_platform, "channels": channels}))
    rds.expire(regkey, 60)

    # get new message
    rdsmsg = rds.brpop(channels['in'], looptime)
    if (rdsmsg is not None):
        logging.info("Cambista received: '%s'" % str(rdsmsg))
        try:
            order_msg = json.loads(rdsmsg[1])
            # pre check data
            order_msg['uid'], order_msg['type']
        except:
            logging.error("Message is not well formatted. Pushed to cambisim:error")
            rds.lpush(channels['error'], str(rdsmsg))
            continue
        if (order_msg['type'] == "order"):
            if ( order_msg['side'] == "buy"):
                order_id = orderbook.buy(order_msg)
            elif ( order_msg['side'] == 'sell'):
                order_id = orderbook.sell(order_msg)
            rds.lpush(channels['new_order'] + order_msg['uid'], json.dumps({ 'type': 'received', 'order_id': order_id}))
            utils.flash("Order '%s' received" % order_id, "info", sync=False)
        elif (order_msg['type'] == "cancel_order"):
            logging.info("Cancel Order '%s'" % order_msg['order_id']) 
            orderbook.cancel_order(order_msg['order_id'])
            rds.lpush(channels['cancel_order'] + order_msg['uid'], json.dumps({ 'type': 'order_cancelled', 'order_id': order_msg['order_id']}))
            utils.flash("Order '%s' cancelled" % order_msg['order_id'], "info", sync=False)
        else:
          logging.warning("Message type unknown in " + str(order_msg))

    # simulate market
    tickers = {}
    for k in  rds.scan_iter(match="cb:mkt:tick:*"):
        pair = k.split(":")[3]
        try:
            tickers[pair] = float(rds.get("cb:mkt:tick:" + pair))
        except ValueError:
            print "No value for ticker '" + pair + "', exiting."
            sys.exit(1)

    i = 0
    delindexes = []
    for order in orderbook.orders:
        ticker = tickers[order['pair']] 
        if ( (ticker >= order['price']) and (order['side'] == "sell") or 
             (ticker <= order['price']) and (order['side'] == "buy")  ):
            logging.info("Order '%s' filled" % order['order_id'])
            delindexes.append(i)
            msg = { "order_id": order['order_id'],
                    "price": ticker, 
                    "product_id": order['pair'], 
                    "reason": "filled", 
                    "remaining_size": "0", 
                    "side": order['side'], 
                    "time": datetime.datetime.now().isoformat(),
                    "type": "done", 
                }
            rds.lpush(channels['order_filled'] + order['order_id'], json.dumps(msg))
            utils.flash("Order '%s' filled" % msg['order_id'], "info", sync=False)
            logging.info("Order filled: " + order['order_id'])
        i += 1
    for di in delindexes:
        orderbook.del_order(di)
