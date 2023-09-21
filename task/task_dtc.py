from typing import Any
from typing_extensions import override
from can import Bus, Message
import engine
import random
import util
import obd

# ref: https://www.csselectronics.com/pages/obd2-explained-simple-intro
class Task_Diagnostic_Control(engine.Task):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.service_ids = [1,2,3,4,6,7]

    @override
    def run(self, bus: Bus):
        return super().run(bus)
    
    @override
    def on_message_received(self, msg: Message):
        if msg.arbitration_id == 0xD0C:
            self.send(0xD1C, msg.data)

    @override
    def get_data(self):
        #values = list(range(len(obd.commands[1])))
        #cmd = obd.commands[1][random.choice(values)]
        #return util.to_can_data(cmd)
        return None,None


    def is_fd(self):
        return True