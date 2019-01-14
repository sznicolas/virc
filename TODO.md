# TODO

## Bugs
### Cambista
#### When collections are empty

* Manage 'rejected' 'post\_only' message from Coinbase:
```
 {u'status': u'rejected', u'created_at': u'2018-12-13T21:44:23.344806Z', u'post_only': True, u'product_id': u'BTC-EUR', u'fill_fees': u'0.0000000000000000', u'reject_reason': u'post only', u'price': u'2925.00000000', u'executed_value': u'0.0000000000000000', u'id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', 'order_id': u'cccccccc-cccc-cccc-cccc-cccccccccccc', u'time_in_force': u'GTC', u'settled': False, u'filled_size': u'0.00000000', u'type': u'limit', u'side': u'buy', u'size': u'0.01000000'}
```

### Trader
#### Verify key error (if stop called twice)
#### When bot is restarted : verify order status
#### Simplebot doesn't like trapping a SIGTERM when bloqued in brpop 
```
trader_1       |   File "/usr/local/lib/python2.7/dist-packages/redis/connection.py", line 636, in read_response
trader_1       |     raise e
trader_1       | TypeError: cannot concatenate 'str' and 'NoneType' objects
```
Not sure every case has been taken into account

## Gui
* dynamically update bots page (in progress)
* get and display account and last filled orders (, ...)
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
...
