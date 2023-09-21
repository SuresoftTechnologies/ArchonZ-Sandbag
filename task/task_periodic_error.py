from typing import Any
from typing_extensions import override
from can import Bus, CanError, Message
import engine


class Task_Periodic_Error(engine.Task):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.recv_count = 0;
        pass 

    @override
    def on_message_received(self, msg: Message):
        self.recv_count += 1
    
    @override
    def get_data(self):
        if self.recv_count % 1024 == 0:
            self.recv_count = 0
            return 0x700, [0xDE, 0xAD, 0xBE, 0xEF]  # error
        else:
            return None, None

    @override
    def run(self, bus: Bus):
        return super().run(bus)
        
    @override
    def is_fd(self):
        return True