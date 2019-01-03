import os, datetime

class SimpleBot(object):
    def __init__(self, bot):
        self.instructions = []
        self.name = bot['name']
        self.pid = os.getpid()
        self.uid = bot['uid']
        self.pair = bot['pair']
        self.sim_mode = bot.get('sim_mode')
        self.status = "running"
        self.start_date = datetime.datetime.now()
        self.instructions_loop = bot.get('instructions_loop')
        self.instructions_index = bot.get('instructions_index', 0)
        self.instructions_count = bot.get('instructions_count', 0)
        for instruction in bot['instructions']:
            if not "pair" in instruction:
                instruction['pair'] = self.pair
            self.instructions.append(Instruction(instruction))

    def to_dict(self):
        return {
            "name": self.name,
            "pid": self.pid,
            "uid": self.uid,
            "type": "simple",
            "pair": self.pair,
            "sim_mode": self.sim_mode,
            "start_date": self.start_date.isoformat(),
            "instructions_loop": self.instructions_loop,
            "instructions_index": self.instructions_index,
            "instructions_count": self.instructions_count,
            "instructions": [ i.to_dict() for i in self.instructions ]
            }

    def get_status(self):
        return self.status

    def issim_mode(self):
        return self.sim_mode

    def next_instruction(self):
        self.instructions_index += 1
        self.instructions_count += 1
        if (self.instructions_index >= len(self.instructions)):
            if (self.instructions_loop):
                self.instructions_index = 0
            else:
                return None
        return self.get_current_instruction()

    def set_current_instruction_wait_order(self, order_id):
        self.instructions[self.instructions_index].set_wait_order_id(order_id)    
    
    def get_current_instruction(self):
        instructions =  self.instructions[self.instructions_index].to_dict()    
        instructions['uid'] = self.uid
        return instructions
    
    def get_instructions(self):
        return iter(self.instructions)

    def get_waited_order_id(self):
        return self.instructions[self.instructions_index].wait_filled

    def set_order_filled(self, order_id):
        self.instructions[self.instructions_index].set_order_filled(order_id)

    def end(self, status="ended"):
        self.status = status

    def __repr__(self):
        return "Bot '{}': ({})".format(str(self.name, self.to_dict()))

class Instruction(object):
    def __init__(self, instruction):
        self.size = instruction['size']
        self.side = instruction['side']
        self.price = instruction['price']
        self.type = instruction['type']
        self.pair = instruction['pair']
        self.wait_filled = instruction.get('wait_filled')
        self.start_date = instruction.get("start_date")
        self.status = instruction.get('status') # "wait_filled"|"cancelled"|None

    def to_dict(self):
        if self.start_date:
            start_date = self.start_date.isoformat()
        else:
            start_date = None
        return { "size": self.size, "side": self.side,
                "price": self.price, "type": self.type,
                "pair": self.pair, "wait_filled": self.wait_filled,
                "start_date": start_date, "status": self.status}

    def get_wait_order_id(self):
        return self.wait_filled

    def set_wait_order_id(self,order_id):
        self.start_date = datetime.datetime.now()
        self.status = "wait_filled"
        self.wait_filled = order_id

    def set_order_filled(self,order_id):
        self.status = None
        self.wait_filled = None

    def cancel(self):
        self.status = "cancelled"

    def __repr__(self):
        return "Instruction ({})".format(str(self.to_dict()))

