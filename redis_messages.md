# Redis messages

## messages from gui to Trader

### Create a simple bot
trader:build type: List

## message from Trader to a new bot
trader:startbot:<uuid>  type: String

## Running bot
trader:rb type: Hash
key: uuid
value: JSON bot status

## Message for flash in gui
gui:message Type: List
Format: JSON { "type": "alert", "message": "Message content" }
