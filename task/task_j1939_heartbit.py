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

class Task_J1939_HeartBit(engine.Task):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._socket = CANSocket(bustype='remote', channel='ws://localhost:54701', bitrate=50000)
        # self._uds = uds.Uds(reqId=0x7E0, resId=0x7E8, transportProtocol="CAN", interface='remote', channel='ws://localhost:54701', bitrate=50000, receive_own_messages=True)
        self._name = "j1939_heartbit"

    @override
    def on_message_received(self, msg: Message):
        pass
    
    @override
    def get_data(self):
        try:
            j1939_message = [CAN(identifier=0x18feca00,length=8, data=b'\x00\xFF\xFF\xFF\x00\xFF\xFF\xFF')]
            # a = self._socket.send(j1939_messages)
            # print(a)
            return 0x18feca00, b'\x00\xFF\xFF\xFF\x00\xFF\xFF\xFF'
            
        except:
            pass
        return None, None


    @override
    def run(self, bus: Bus):
        return super().run(bus)
        
    @override
    def is_fd(self):
        return True