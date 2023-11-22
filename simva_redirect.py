import time
import can
import argparse


parser = argparse.ArgumentParser("SimVA to CAN Remote Bus", "It will redirect SimVA to CAN Remote Bus")
parser.add_argument('--channel', '-c', dest='channel', required=True, type=int, help='SimVA has various channel. Please specify channel number(check cfg file in simva).')

def run(channel: int):
    bus = can.Bus(interface='remote', channel='ws://localhost:54701', bitrate=50000, receive_own_messages=True)
    simva = can.Bus(interface='simva', channel=channel)
    print('Initialize')
    while True:
        
        simva_msg = simva.recv()
        remote_msg = bus.recv(1)
        
        # if there is no message, continue
        if simva_msg is None and remote_msg is None:
            continue
        
        
        # send to CAN Remote Bus
        if simva_msg is not None:
            bus.send(simva_msg)
        
        # and also send to SimVA from CAN Remote Bus
        if remote_msg is not None:
            simva.send(remote_msg)
            print(remote_msg)
        
        # wait for 10ms
        # it is not a stress test, give some time to SimVA
        time.sleep(0.01)


opt = parser.parse_args()
run(opt.channel)
