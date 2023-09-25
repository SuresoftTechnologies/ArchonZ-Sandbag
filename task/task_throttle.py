from typing import Any
from typing_extensions import override
from can import Bus, Message
import engine
import random
import util
import time

class Task_Throttle_Control(engine.Task):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._speed = 0
        self._rpm = 0
        self._init = False

    @override
    def run(self, bus: Bus):
        return super().run(bus)
    
    def reset(self):
        self._init = False
        self._speed = 0
        self._rpm = 0
        self.send(0xEEE, [0xDE, 0xAD, 0xBE, 0xEF])  # reset mark

        # welcome light
        for i in range(255):
            time.sleep(0.01)
            self._speed = i
            self._rpm = i * 100
            rpm_byte_value = self.get_rpm_bytes()
            self.send(0xEEE, [self._speed, rpm_byte_value[0], rpm_byte_value[1], 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        
        self._init = True
    
    @override
    def on_message_received(self, msg: Message):

        if util.obd_util.is_request(msg):
            if len(msg.data) > 3:
                length = msg.data[0]
                mode = msg.data[1]
                subfn = msg.data[2]
                # ECU Reset
                if mode == 0x11 and subfn == 0x01:
                    print('ECU RESET')
                    # send reset request
                    self.reset()

                    # Success
                    self.send(0x7E8, [0x02, 0x51, 0x01])
                    #                 len,  ok,   subfn
                    pass 

            # Show stored Diagnostic Trouble Codes
            elif mode == 0x03:
                dtc_categories = [0x0, 0x1, 0x2, 0x3] 
                # P(b00) power train
                # C(b01) chasis
                # B(b10) body
                # U(b11) network
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
                pass
            elif mode == 0x01:
                pid = msg.data[2]
                # request for vehicle speed
                if pid == 0x0D:
                    data = [
                        3,
                        (mode)+0x40,
                        0x0D,
                        self.get_current_speed(),
                        0,
                        0,
                        0,
                        0
                    ]
                    self.send(0x7E8, data)
                # request for rpm
                elif pid == 0x0C:
                    rpm_byte_value = self.get_rpm_bytes()
                    data = [
                        4,
                        (mode)+0x40,
                        0x0C,
                        rpm_byte_value[0],
                        rpm_byte_value[1],
                        0,
                        0,
                        0
                    ]
                    self.send(0x7E8, data)

    
    @override
    def get_data(self):
        if self._init:
            # some logic
            self._speed += 1
            self._speed = self._speed % 255

            self._rpm += 10
            self._rpm = self._rpm % 16384

            # broadcast information to other ecu
            rpm_byte_value = self.get_rpm_bytes()
            return 0xEEE, [self._speed, rpm_byte_value[0], rpm_byte_value[1], 0x0, 0x0, 0x0, 0x0, 0x0]
        else:
            self.reset()
            return None, None
        
    @override
    def is_fd(self):
        return True
    
    def get_current_speed(self):
        return self._speed
    
    def get_rpm_bytes(self):
        return self._rpm.to_bytes(2, 'big')