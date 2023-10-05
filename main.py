# system
import time
import multiprocessing
import argparse

# 3rdparty
import can
import can_remote

# ours
import engine
import task
import services

parser = argparse.ArgumentParser("sandbag", "for emulator for virtual can bus via websocket")
parser.add_argument('--overflow_off', action='store_true', help='overflow error signal off')
parser.add_argument('--vehicle_off', action='store_true', help='speed, rpm signal off')
parser.add_argument('--heartbit_off', action='store_true', help='periodic heart bit signal off')
parser.add_argument('--dtc_off', action='store_true', help='dtc signal handler off')
parser.add_argument('--periodic_error_off', action='store_true', help='some error will be raised with signal(ID: 0x700)')
opt = parser.parse_args()


def main():
    time.sleep(1)   # for server on
    print('Sandbag Started')
    
    bus = can.Bus(interface='remote', channel='ws://localhost:54701', bitrate=50000, receive_own_messages=True)
    e = engine.Engine(bus)
    
    if not opt.vehicle_off:
        e.register_task(task.Task_Throttle_Control(), [], 0.01)
    if not opt.dtc_off:
        e.register_task(task.Task_Diagnostic_Control(), [], 1)
    
    if not opt.heartbit_off:
        e.register_task(task.Task_HeartBit(), [], 1)

    if not opt.overflow_off:
        e.register_task(task.Task_Overflow_Checker(), [], 0.01)
    
    if not opt.periodic_error_off:
        e.register_task(task.Task_Periodic_Error(), [], 0.1)

    e.start() 


def remote_server():    
    print('Server Started')

    config = {}
    config["channel"] = 0
    config["bustype"] = 'virtual'
    config["bitrate"] = 500000

    server = can_remote.RemoteServer('0.0.0.0', 54701, **config)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print('Server Closed')


def vsomeip_service():
    services.run_service('127.0.0.1', '224.255.226.233', 30509)


if __name__ == "__main__":
    p1 = multiprocessing.Process(target=remote_server)
    p2 = multiprocessing.Process(target=main)
    p3 = multiprocessing.Process(target=vsomeip_service)
    p1.start()
    p2.start()
    p3.start()

    p1.join()
    p2.join()
    p3.join()
