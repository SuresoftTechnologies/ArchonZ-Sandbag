from typing import Any
from typing_extensions import override
from can import Bus, CanError, Message
import engine
import random
import util
import obd
import uds

from scapy.all import *
from scapy.layers.can import *
from scapy.contrib.cansocket_python_can import *
from scapy.contrib.automotive.ccp import *
from scapy.contrib.automotive.obd.obd import *
from scapy.contrib.isotp import *

class Task_HeartBit(engine.Task):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._socket = CANSocket(bustype='remote', channel='ws://localhost:54701', bitrate=50000)
        self._uds = uds.Uds(reqId=0x7E0, resId=0x7E8, transportProtocol="CAN", interface='remote', channel='ws://localhost:54701', bitrate=50000, receive_own_messages=True)

    @override
    def on_message_received(self, msg: Message):
        pass
    
    @override
    def get_data(self):
        mode = random.choice([0x01,     #  mode 1. real time data
                               0x03,    # get dtc
                               0xFF,    # UDS
                               0xFF,    # UDS
                               0xFF,    # UDS
                               ])
        choice = random.choice([0x0D,   # vehicle speed
                                0x0C,   # rpm
                                ])
        
        if mode == 0x03:
            data = [
                        1,
                        mode,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0
                    ]
        elif mode == 0x01:
            data = [
                2,
                mode,     
                choice,
                0,
                0,
                0,
                0,
                0
            ]
        elif mode == 0xFF:
            try:
                messages = [CAN(identifier=0x7ff,length=8, data=b'\x01\x02\x03\x04\x05\x06\x07\x08'),
                            CAN(identifier=0x7ff,length=8, data=b'\x02\x03\x04\x05\x05\x06\x07\x08'),
                            CAN(identifier=0x7ff,length=8, data=b'\x01\x01\x01\x05\x01\x01\x07\x01'),
                            CAN(identifier=0x7ff,length=8, data=b'\x03\x01\x01\x04\x01\x01\x04\x01'),
                            OBD()/OBD_S01(pid=0)
                            ]
                self._socket.send(random.choice(messages))
                
                
                if random.choice([True, False]):
                    a = self._uds.send([0x11, 0x22, 0x33])
                    print(a)
                else:
                    a = self._uds.send([0x33, 0x22, 0x11])
                    print(a)
                
            except:
                pass
            return None, None

       
        return util.REQUEST_ID, data

    @override
    def run(self, bus: Bus):
        return
        
    @override
    def is_fd(self):
        return True