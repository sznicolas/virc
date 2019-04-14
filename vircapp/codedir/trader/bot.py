import os, datetime, copy, json
from utils import Cambista
# import dateutil.parser
from json_logic import jsonLogic

rbs = "trader:rb" # redis hash containing running bot status
hbs = "trader:hb" # redis hash containing history of ended bot status

class Bot(object):
    def __init__(self, bot, rds):
        self.rds  = rds
        self.name = bot['name']
        self.pid  = os.getpid()
        self.uid  = bot['uid']
        self.status = "running"
        self.start_date = datetime.datetime.now()
        self.instruction_book = InstructionsBook(bot.get('instruction_book'), self.uid)
        self.tprofit = bot.get("tprofit")
        self.tpprofit = bot.get("tpprofit")

    def to_dict(self):
        return {
            "name": self.name,
            "pid": self.pid,
            "uid": self.uid,
            "type": self.type,
            "status": self.status,
            "start_date": self.start_date.isoformat(),
            "instruction_book": self.instruction_book.to_dict(),
            "tprofit" : self.tprofit,
            "tpprofit" : self.tpprofit
            }

    def iter_instructions(self):
        return self.instruction_book.iter_instructions()

    def get_status(self):
        return self.status

    def get_current_instruction(self):
        return self.instruction_book.current_instruction.to_dict()    

    def cancel_current_instruction(self):
        self.instruction_book.current_instruction.cancel()

    def end(self, status="ended"):
        self.status = status

    def update_blueprint(self):
        if (self.get_status() == "running"):
            channel = rbs + ":" + self.uid
        else:
            channel = hbs + ":" + self.uid
            self.rds.delete(rbs + ":" + self.uid)
        self.rds.delete(channel)
        self.rds.set(channel, json.dumps(self.to_dict()))

    def __repr__(self):
        return "Bot '{}': ({})".format(self.name, str(self.to_dict()))

class OrderBot(Bot):
    def __init__(self, bot, rds):
        super(OrderBot, self).__init__(bot, rds)
        self.type = bot.get("type", "orderbot")
        self._set_theorical_profit()
        self.cambista_link  = bot['cambista_link']
        self.get_cambista_def()

    def get_cambista_def(self):
        # get cambista channels
        self.cambista = Cambista(json.loads(self.rds.get(self.cambista_link)))

    def cancel_order(self):
        # send cancel order before the others with rpush
        self.rds.rpush(self.cambista.c_in(), json.dumps( { 'type': "cancel_order",
                "order_id": self.get_order_id(), 'uid': self.uid } ))
        self.rds.brpop(self.cambista.c_cancel_order() + self.uid)[1]
        self.cancel_current_instruction()

    def send_order(self):
        if (self.instruction_book.current_instruction.get_type() == "order_var"):
            mktprice = self.rds.get("cb:mkt:tick:" + self.instruction_book.current_instruction.get_pair())
            self.instruction_book.current_instruction.set_price(mktprice)
        res = self.rds.lpush(self.cambista.c_in(), json.dumps(self.get_current_instruction()))
        # wait order_id
        msg = self.rds.brpop(self.cambista.c_new_order() + self.uid)
        msg = json.loads(msg[1])
        if ( msg['type'] == "refused"):
            self.error = msg
            return None
        return msg['order_id']

    def set_order_id(self,order_id):
        self.instruction_book.current_instruction.set_order_id(order_id)

    def wait_order_update(self):
        msg = {}
        try:
            msg = json.loads(self.rds.brpop(self.cambista.c_order_done() + self.get_order_id())[1])
        except Exception as e:
            print("Error probably due to redis's brpop while exiting. '%s'" % e)
        return msg

    def get_order_status(self):
        msg = ""
        self.rds.lpush(self.cambista.c_in(), 
                json.dumps({'type' : 'get_order_status', 'order_id': self.get_order_id(), 'uid': self.uid}))
        try:
            msg = json.loads(self.rds.brpop(self.cambista.c_order_status() +  self.get_order_id())[1])
        except Exception as e :
            print("Error probably due to redis's brpop while exiting")
        return msg

    def get_order_id(self):
        return self.instruction_book.current_instruction.get_order_id()
    
    def set_order_filled(self, waited_order_id):
        return self.instruction_book.current_instruction.set_order_filled(waited_order_id)

    def _set_theorical_profit(self):
        if (self.instruction_book.instructions[0].type == "order_var" or 
                self.instruction_book.instructions[1].type == "order_var"):
            self.tprofit = None
            self.tpprofit = None
            return None
        s0 = self.instruction_book.instructions[0].price * self.instruction_book.instructions[0].size 
        s1 = self.instruction_book.instructions[1].price * self.instruction_book.instructions[1].size 
        if (self.instruction_book.instructions[0].side == 'buy'):
            self.tprofit = s1 - s0
            self.tpprofit = self.tprofit * 100 / s0
        else:
            self.tprofit = s0 - s1
            self.tpprofit = self.tprofit * 100 / s1

    def to_dict(self):
        d = super(OrderBot, self).to_dict()
        d['type'] = self.type
        d["cambista_link"]  = self.cambista_link
        d["cambista"] = self.cambista.to_dict()
        return d

class CondBot(OrderBot):
    def __init__(self, bot, rds):
        super(CondBot, self).__init__(bot, rds)
        self.type = bot.get("type", "condbot")

    def _set_theorical_profit(self):
        pass
    
    def evaluate_current_instruction(self, indicators):
        self.instruction_book.current_instruction.evaluate(indicators)

    def cancel_instruction(self):
        if self.instruction_book.current_instruction.get_type() == "order":
            self.cancel_order()

class InstructionsBook(object):
    """ contains active instructions 
    and archives closed instructions """
    def __init__(self, ibk, uid):
        self.loop  = ibk.get("loop")
        self.index = ibk.get("index", 0)
        self.count = ibk.get("count", 0)
        self.pair  = ibk.get('pair') #default pair if not set in an instruction.
        self.uid   = uid
        self.history = []
        self.instructions = []
        if ibk.get("history"):
            self._load_instructions(ibk['history'], self.history)
        self._load_instructions(ibk['instructions'], self.instructions)
        if ibk.get('current_instruction'):
            self.current_instruction = self._create_instruction(ibk['current_instruction'])
        else:
            self.current_instruction = copy.deepcopy(self.instructions[self.index])
        self.current_instruction.set_uid(self.uid)

    def to_dict(self):
        return {
                "loop": self.loop,
                "index": self.index,
                "count": self.count,
                "uid"  : self.uid,
                "pair" : self.pair,
                "instructions": [ i.to_dict() for i in self.instructions ],
                "history": [ i.to_dict() for i in self.history ],
                "current_instruction": self.current_instruction.to_dict()
                }

    def _load_instructions(self, source, dest):
        for instruction in source:
            if not "pair" in instruction.keys():
                instruction['pair'] = self.pair
            dest.append(self._create_instruction(instruction))

    def _create_instruction(self, instruction):
        if instruction['type'] == "order":
            return OrderInstruction(instruction)
        elif instruction['type'] == "order_var":
            return OrderVarInstruction(instruction)
        elif instruction['type'] == "conditionnal":
            return CondInstruction(instruction)
        else:
            raise Exception("instruction['type'] not implemented. was: '{}'".format(instruction['type']))

    def iter_instructions(self):
        while (self.index < len(self.instructions)):
            yield self.current_instruction
            self.history.append(self.current_instruction)
            self.index += 1
            self.count += 1
            if (self.index >= len(self.instructions)):
                if (self.loop is True):
                    self.index = 0
                else:
                    raise StopIteration
            self.current_instruction = copy.deepcopy(self.instructions[self.index])
            self.current_instruction.set_uid(self.uid)
            self.current_instruction.set_start_date()

class Instruction(object):
    """ generic instruction base class """
    def __init__(self, instruction):
        self.uid  = instruction.get('uid')
        self.type = instruction['type']
        self.execution_date = instruction.get("execution_date")
        self.start_date     = instruction.get("start_date")
        self.cancel_date    = instruction.get("cancel_date")

    def set_uid(self, uid):
        self.uid = uid

    def cancel(self):
        self.cancel_date = datetime.datetime.now()
        self.status = "canceled"

    def get_type(self):
        return self.type

    def set_execution_date(self, execdate=None):
        if execdate:
            self.execution_date = execdate
        else:
            self.execution_date = datetime.datetime.now()

    def set_start_date(self, startdate=None):
        if startdate:
            self.startdate = startdate
        else:
            self.startdate = datetime.datetime.now()

    def _idate(self, d):
        """ transforms date to isoformat or None if date is not set """
        if d:
            if isinstance(d, datetime.datetime):
                return d.isoformat()
            return d # probably isoformat 'str' previously modified, in case of a bot reloaded.
        else:
            return None

    def get_pair(self):
        return self.pair

class OrderInstruction(Instruction):
    """ order instruction. buy or sell at a defined price """
    def __init__(self, instruction):
        super(OrderInstruction, self).__init__(instruction)
        self.size = instruction['size']
        self.side = instruction['side']
        self.price = instruction['price']
        self.pair = instruction['pair']
        self.wait_filled = instruction.get('wait_filled')
        self.order_id = instruction.get('order_id')
        self.status = instruction.get('status') # "wait_filled"|"canceled" <= with one 'l' |"filled"|None

    def to_dict(self):
        return { "size": self.size,  "side"  : self.side,
                "price": self.price, "type"  : self.type,
                "pair" : self.pair,  "status": self.status,
                "uid"  : self.uid,   "order_id": self.order_id,
                "wait_filled": self.wait_filled,
                "start_date" : self._idate(self.start_date),
                "execution_date": self._idate(self.execution_date),
                "cancel_date": self._idate(self.cancel_date)
                }

    def get_order_id(self):
        return self.order_id

    def set_order_id(self,order_id):
        self.status = "wait_filled"
        self.wait_filled = order_id
        self.order_id = order_id

    def set_order_filled(self,order_id):
        self.set_execution_date()
        self.status = "filled"
        self.order_id = order_id
        self.wait_filled = None

    def __repr__(self):
        return "OrderInstruction ({})".format(str(self.to_dict()))

class OrderVarInstruction(OrderInstruction):
    """ variable order instruction.
    set an order price relative to market price """
    def set_price(self, mktprice):
        _, val = self.price.split("mkt:")
        self.price = float(val) + float(mktprice)
        self.type = "order"

class CondInstruction(Instruction):
    """ conditionnal instruction.
    evaluate logic and returns result """
    def __init__(self, instruction):
        super(CondInstruction, self).__init__(instruction)
        self.data  = instruction.get('data')
        self.rules = instruction.get('rules')
        self.pair  = instruction['pair']

    def to_dict(self):
        return {
            "data" : self.data,
            "rules": self.rules,
            "pair" : self.pair,
            "type" : self.type,
            "start_date" : self._idate(self.start_date),
            "execution_date": self._idate(self.execution_date),
            "cancel_date": self._idate(self.cancel_date)
        }

    def evaluate(self, indicators):
        for k1 in self.data.keys():
            for k2 in self.data[k1].keys():
                self.data[k1][k2] = indicators[k1][k2]
        self.set_execution_date()
        return jsonLogic(self.rules, self.data)

