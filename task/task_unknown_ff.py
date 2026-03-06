from typing import Any
from typing_extensions import override
from can import Bus, Message
import engine


class Task_Unknown_FF(engine.Task):
    """
    미인식 ECU Arbitration ID로 ISO-TP First Frame을 주기적으로 전송한다.
    드라이버 측 IsoTp.indication() / indication_all()이 FC-OVFLW로 응답하는지 검증하기 위한 task.

    FC-OVFLW 수신 시 fc_ovflw_received 플래그를 True로 설정하고 로그를 출력한다.
    """

    FC_FRAME_TYPE = 0x3
    FC_FS_OVFLW = 2

    def __init__(self, unknown_id=0x321, *args: Any, **kwargs: Any) -> None:
        self._name = "unknown_ff_sender"
        self.unknown_id = unknown_id
        self.fc_ovflw_received = False
        self.fc_ovflw_count = 0

    @override
    def on_message_received(self, msg: Message):
        try:
            if msg.arbitration_id != self.unknown_id:
                return
            if not msg.data or len(msg.data) < 3:
                return
            frame_type = (msg.data[0] >> 4) & 0xF
            if frame_type == self.FC_FRAME_TYPE:
                fs = msg.data[0] & 0xF
                if fs == self.FC_FS_OVFLW:
                    self.fc_ovflw_received = True
                    self.fc_ovflw_count += 1
                    print(f"[Task_Unknown_FF] FC-OVFLW received for unknown ID 0x{self.unknown_id:X} (count={self.fc_ovflw_count})")
        except Exception:
            pass

    @override
    def get_data(self):
        # First Frame: PCI upper nibble=1 (FF), FF_DL=0x00A (10 bytes)
        return self.unknown_id, [0x10, 0x0A, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]

    @override
    def run(self, bus: Bus):
        return super().run(bus)

    @override
    def is_fd(self):
        return True
