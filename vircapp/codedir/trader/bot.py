import os, datetime, copy
# import dateutil.parser

class SimpleBot(object):
    def __init__(self, bot):
        self.name = bot['name']
        self.pid = os.getpid()
        self.uid = bot['uid']
        self.pair = bot['pair']
        self.cambista_link  = bot['cambista_link']
        self.cambista_title = bot.get('cambista_title')
        self.cambista_icon  = bot.get('cambista_icon')
        self.status = "running"
        self.start_date = datetime.datetime.now()
        self.instructions_loop = bot.get('instructions_loop')
        self.instructions_index = bot.get('instructions_index', 0)
        self.instructions_count = bot.get('instructions_count', 0)
        self.instructions_history = []
        if bot.get("instructions_history"):
            for instruction in bot['instructions_history']:
                self.instructions_history.append(Instruction(instruction))
        self.instructions = []
        for instruction in bot['instructions']:
            if not "pair" in instruction:
                instruction['pair'] = self.pair
            self.instructions.append(Instruction(instruction))
        if bot.get('current_instruction'):
            self.current_instruction = Instruction(bot.get('current_instruction'))
        else:
            self.current_instruction = Instruction(self.instructions[self.instructions_index])
        self.current_instruction.set_uid(self.uid)

    def to_dict(self):
        return {
            "name": self.name,
            "pid": self.pid,
            "uid": self.uid,
            "type": "simple",
            "status": self.status,
            "pair": self.pair,
            "cambista_link": self.cambista_link,
            "cambista_title": self.cambista_title,
            "cambista_icon": self.cambista_icon,
            "start_date": self.start_date.isoformat(),
            "instructions_loop": self.instructions_loop,
            "instructions_index": self.instructions_index,
            "instructions_count": self.instructions_count,
            "instructions": [ i.to_dict() for i in self.instructions ],
            "instructions_history": [ i.to_dict() for i in self.instructions_history ],
            "current_instruction": self.current_instruction.to_dict()
            }

    def get_status(self):
        return self.status

    def get_cambista_link(self):
        return self.cambista_link

    def iter_instructions(self):
        while (self.instructions_index < len(self.instructions)):
            yield self.current_instruction
            self.instructions_history.append(self.current_instruction)
            self.instructions_index += 1
            self.instructions_count += 1
            if (self.instructions_index >= len(self.instructions)):
                if (self.instructions_loop is True):
                    self.instructions_index = 0
                else:
                    raise StopIteration
            self.current_instruction = copy.deepcopy(self.instructions[self.instructions_index])
            self.current_instruction.set_uid(self.uid)

    def get_current_instruction(self):
        return self.current_instruction.to_dict()    

    def end(self, status="ended"):
        self.status = status

    def __repr__(self):
        return "Bot '{}': ({})".format(self.name, str(self.to_dict()))

class Instruction(object):
    def __init__(self, instruction):
        self.size = instruction['size']
        self.side = instruction['side']
        self.price = instruction['price']
        self.type = instruction['type']
        self.pair = instruction['pair']
        self.uid  = instruction.get('uid')
        self.wait_filled = instruction.get('wait_filled')
        self.start_date = instruction.get("start_date")
        self.filled_date = instruction.get("filled_date")
        self.cancel_date = instruction.get("cancel_date")
        self.status = instruction.get('status') # "wait_filled"|"canceled" <= with one 'l' !!! |"filled"|None

    def to_dict(self):
        return { "size": self.size,  "side"  : self.side,
                "price": self.price, "type"  : self.type,
                "pair" : self.pair,  "status": self.status,
                "uid"  : self.uid,
                "wait_filled": self.wait_filled,
                "start_date" : self._idate(self.start_date),
                "filled_date": self._idate(self.filled_date),
                "cancel_date": self._idate(self.cancel_date)
                }

    def _idate(self, d):
        """ transforms date to isoformat or None if date is not set """
        if d:
            if isinstance(d, datetime.datetime):
                return d.isoformat()
            return d # probably isoformat 'str' previously modified, in case of a bot reloaded.
        else:
            return None

    def get_order_id(self):
        return self.wait_filled

    def set_uid(self, uid):
        self.uid = uid

    def set_order_id(self,order_id):
        self.start_date = datetime.datetime.now()
        self.status = "wait_filled"
        self.wait_filled = order_id

    def set_order_filled(self,order_id):
        self.filled_date = datetime.datetime.now()
        self.status = "filled"
        self.wait_filled = None

    def cancel(self):
        self.cancel_date = datetime.datetime.now()
        self.status = "canceled"

    def __repr__(self):
        return "Instruction ({})".format(str(self.to_dict()))

