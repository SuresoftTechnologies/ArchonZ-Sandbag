from typing import Any
from typing_extensions import override
from can import Bus, CanError, Message
import engine

class Task_Stop_Controller(engine.Task):
    def __init__(self, engine_instance=None, can_id=0x7c6, payload=None, *args: Any, **kwargs: Any) -> None:
        self._name = "stop_controller"
        self._engine = engine_instance  # Engine 인스턴스를 저장할 변수
        self.can_id = can_id
        self.payload = payload or [0x01, 0x28, 0x03, 0x00, 0xAA, 0xAA, 0xAA, 0xAA]
        print(f"Stop Controller created with ID: 0x{can_id:X}, Payload: {self.payload}")
        pass
    
    @override
    def on_message_received(self, msg: Message):
        # 특정 ID를 가진 메시지가 수신되면 stop_all_task 호출
        # 예: 0x800 ID를 가진 메시지가 오면 모든 태스크 중지
        if msg.arbitration_id == self.can_id:
            if list(msg.data) == self.payload:
                print(f"Stop command received: {msg}")
                if self._engine:
                    self._engine.stop_all_task()
                else:
                    print("ERROR: Engine 인스턴스가 None입니다!")
    
    @override
    def get_data(self):
        # 이 태스크는 데이터를 보내지 않음
        return None, None
    
    @override
    def run(self, bus: Bus):
        return super().run(bus)
        
    @override
    def is_fd(self):
        return True