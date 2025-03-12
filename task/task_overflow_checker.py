from typing import Any
from typing_extensions import override
from can import Bus, CanError, Message
import engine


class Task_Overflow_Checker(engine.Task):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._OVERFLOW = False
        self.length = {}
        self._name = "overflow_checker"
        pass 

    @override
    def on_message_received(self, msg: Message):
        self.length[msg.arbitration_id] = len(msg.data)

        for k, l in self.length.items():   
            if l > 64 and l <= 70:
                print(f'{k:02X} is overflow')
                self._OVERFLOW = True
                del self.length[msg.arbitration_id]
                return
        
        
    
    @override
    def get_data(self):
        if not self._OVERFLOW:
            return 0x7AA, [0x01, 0x02, 0x03]  # ok
        else:
            self._OVERFLOW = False
            return 0xFFF, [0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]  # fail


    @override
    def run(self, bus: Bus):
        return super().run(bus)
        
    @override
    def is_fd(self):
        return True