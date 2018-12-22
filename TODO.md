# TODO

## Bugs
### Cambista
#### When collections are empty

Manage 'rejected' 'post\_only' message from Coinbase:
```
 {u'status': u'rejected', u'created_at': u'2018-12-13T21:44:23.344806Z', u'post_only': True, u'product_id': u'BTC-EUR', u'fill_fees': u'0.0000000000000000', u'reject_reason': u'post only', u'price': u'2925.00000000', u'executed_value': u'0.0000000000000000', u'id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', 'order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'time_in_force': u'GTC', u'settled': False, u'filled_size': u'0.00000000', u'type': u'limit', u'side': u'buy', u'size': u'0.01000000'}
```

At the very first launch, collections are empty and there is some caveats. The main workaround is to relaunch after data is grabbed by the grabber, for the `pairs` defnied in [conf.env](vircapp/conf.env). 
* Analyst: `File "[/code/mkstats.py](vircapp/codedir/analyst/mkstats.py)", line 95 p =  db[c].find_one()['product_id']` returns None.
* utils.py: gets the redis string `virc:convproducts` which is empty. Returns an error.

TODO: Get all pairs available, let the user select the wanted pairs in the gui.

#### Take in account when a order is manually cancelled
nform bots when this kind of message is received :
```
{u'user_id': u'cccccccccccccccccccccccc', u'product_id': u'BTC-EUR', u'remaining_size': u'0.02000000', u'sequence': 4895937579, u'order_id': u'25940140-a1d3-4682-b391-51a5e7182c21', u'price': u'3424.27000000', u'profile_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'reason': u'canceled', u'time': u'2018-12-22T16:33:11.418000Z', u'type': u'done', u'side': u'sell'}
```

### grabber
On websocket error, should be halted and rerun by docker-compose.

## Gui
* display price when picking the price/size
* verify if sell price is higher than buy price
* get and display account and last filled orders (, ...)
* add a nice panel with market informations (or 
* alert when a container loops restart

## Architecture
* prefix all coinbase-specific containers by cb<container>

## Maintenance
* mongodb: mapReduce old market data

## Functionnalities
* Simplebot: add stop loss
* Implement other bots (SimpleStopLoss who can cancel all or a part of existing orders, rangebot, ...)

## Other

* Update doc
* Upload new arch
...
