
from can import Message
from obd import OBDCommand, commands

REQUEST_ID = 0x7DF

DTC_CATEGORY_POWER_TRAIN = 0x0
DTC_CATEGORY_CHASIS = 0x1
DTC_CATEGORY_BODY = 0x2
DTC_CATEGORY_NETWORK = 0x3

#https://www.csselectronics.com/pages/obd2-pid-table-on-board-diagnostics-j1979
#cmd:obd.OBDCommand = obd.commands['SPEED']

def to_can_data(cmd: OBDCommand):
    can_id = int(chr(cmd.header[0]), 16) << 8 | int(chr(cmd.header[1]), 16) << 4 | int(chr(cmd.header[2]),16) 
    data = [
        cmd.bytes, 
        cmd.mode, 
        cmd.pid, 
    ]+list(cmd.command)+[0] # 5 bytes

    return can_id, data



def is_request(msg: Message):
    return msg.arbitration_id == REQUEST_ID

def is_response(msg: Message):
    return msg.arbitration_id in range(0x7E8, 0x7EF)
