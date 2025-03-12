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
        self._name = "diagnostic_control"

    @override
    def run(self, bus: Bus):
        return super().run(bus)
    
    @override
    def on_message_received(self, msg: Message):
        if util.is_request(msg):
            mode = msg.data[1]
            # Show stored Diagnostic Trouble Codes
            if mode == 0x03:
                
                dtc_category = 0x03
                dtc_code = 0x3FFF #[0, 8191]
                dtc_code = (dtc_category<<14)|dtc_code

                code1 = list(int.to_bytes(dtc_code, 2, 'big'))
                code2 = [0,0]
                #code3 = [0,0]
                #unused = [0,0]
                NA = 0xAA
                data = [
                         4,
                         (mode)+0x40,
                         NA
                        ] + code1 + code2 + [0]
                        
                # data = code1 + code2 + code3 + unused
                self.send(0x7E8, data)

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