from typing import Any
from typing_extensions import override
from can import Bus, CanError, Message
import engine

class Task_Resume_Controller(engine.Task):
    def __init__(self, engine_instance=None,can_id=0x7c6, payload=None, *args: Any, **kwargs: Any) -> None:
        self._name = "resume_controller"
        self._engine = engine_instance
        self.can_id = can_id
        self.payload = payload or [0x01, 0x10, 0x00, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA]
        print(f"Resume Controller created with ID: 0x{can_id:X}, Payload: {self.payload}")

    @override
    def on_message_received(self, msg: Message):
        # 예: 0x801 ID를 가진 메시지가 오면 태스크 재개
        if msg.arbitration_id == self.can_id:
            if list(msg.data) == self.payload:
                print(f"Resume command received: {msg}")
                if self._engine:
                    self._engine.resume_all_tasks()
                else:
                    print("ERROR: Engine 인스턴스가 None입니다!")
    
    @override
    def get_data(self):
        return None, None
    
    @override
    def run(self, bus: Bus):
        return super().run(bus)
        
    @override
    def is_fd(self):
        return True