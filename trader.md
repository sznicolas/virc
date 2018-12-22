Warning !
Message formats may have changed.

## message from trade to simplebot
A message is read by the simple bot in his initialization phase.
This type of message is sent to redis, in a list, named `trader:rb:<uuid>` , as his uuid is sent when a bot is started.
The message is a JSON formatted string.

### Message definition

#### Header
Name                        | type   | example     | mandatory | observations
----------------------------|--------|-------------|-----------|--------------
type                        | text   | simple      | Yes       | set to "simple" to start a simple\_bot
instructions\_default\_pair | text   | eur-btc     | No        | if set, used is instruction unless overriden
instructions\_loop          | bool   | True        | No        | default: False
instruction\_next\_index    | int    | 3           | No        | next instruction to execute (starts to 0, default: 0) 
instructions                | array  | _see below_ | Yes       |

#### Instructions definition
Instructions are passed in an JSON array.

Name                       | type            | example                      | mandatory | observations
---------------------------|-----------------|------------------------------|-----------|--------------
size                       | float           | 1.25                         | Yes       | 
side                       | string          | buy                          | Yes       | buy or sell
price                      | string or float | "market +1.1%" or 5000       | Yes       | must be a numerical value, or "market +/-n.nn%"
instruction\_wait          | hash            | {'order\_filled': 'order\_id'} | No        | wait for an event before execute this intruction
post\_only                 | bool            | False (Default: True)        | No        | If set to False, fees may be applied

##### instruction\_wait
if set, at least one of those conditions must be defined. If many, are combined with a logical AND operator.

Name                         | type               | observations
-----------------------------|--------------------|--------------
order\_filled                | coinbase order uid | At least one    
price\_below                 | float              | 
price\_above                 | float              |
volume\_below, volume\_above | hash               | {'<time\_period>': float} where time\_period is "last\_60m", 15m, 05m or 01m 

## Example
`lpush(trader:rb:<uuid>, msg)`
  where msg contains :
```
{type: "simple", 
        instructions_default_pair: "eur-btc", 
        instructions: [ 
           { size : '0.1', sell: '9999.99', instruction_wait: {'order_filled': 'cccccccc-cccc-cccc-cccc-cccccccccccc'}},
           {side: 'buy', size: '0.1', price: 5000 }
        ],
        instructions_loop: True,
        instruction_next_index: 0
}
```

