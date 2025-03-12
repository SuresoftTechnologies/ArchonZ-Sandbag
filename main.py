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
parser.add_argument('--uds_heartbit_off', action='store_true', help='periodic uds heartbeat signal off')
parser.add_argument('--j1939_heartbit_off', action='store_true', help='periodic j1939 heartbeat signal off')
parser.add_argument('--dtc_off', action='store_true', help='dtc signal handler off')
parser.add_argument('--periodic_error_off', action='store_true', help='some error will be raised with signal(ID: 0x700)')

# 새로운 stop/resume 관련 옵션 추가
parser.add_argument('--can_demo_on', action='store_true', help='disable stop controller task')

parser.add_argument('--stop_id', type=str, default='0x7c6', help='CAN ID for stop command (hex format)')
parser.add_argument('--stop_payload', type=str, default='09 28 00 00 AA AA AA AA', help='payload for stop command (space separated hex bytes)')
parser.add_argument('--resume_id', type=str, default='0x7c6', help='CAN ID for resume command (hex format)')
parser.add_argument('--resume_payload', type=str, default='01 10 00 AA AA AA AA AA', help='payload for resume command (space separated hex bytes)')

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
    if not opt.uds_heartbit_off:
        e.register_task(task.Task_Uds_HeartBit(), [], 0.5)
    if not opt.j1939_heartbit_off:
        e.register_task(task.Task_J1939_HeartBit(), [], 0.5)

    if not opt.overflow_off:
        e.register_task(task.Task_Overflow_Checker(), [], 0.01)
    
    if not opt.periodic_error_off:
        e.register_task(task.Task_Periodic_Error(), [], 0.1)

    if opt.can_demo_on:
        stop_id = int(opt.stop_id, 16)
        stop_payload = [int(b, 16) for b in opt.stop_payload.split()]
        stop_controller = task.Task_Stop_Controller(e, stop_id, stop_payload)
        e.register_task(stop_controller, [], 0.1)

        resume_id = int(opt.resume_id, 16)
        resume_payload = [int(b, 16) for b in opt.resume_payload.split()]
        resume_controller = task.Task_Resume_Controller(e, resume_id, resume_payload)
        e.register_task(resume_controller, [], 0.1)

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

def doip_service():
    services.run_doip()


if __name__ == "__main__":
    processes = []

    p1 = multiprocessing.Process(target=remote_server)
    p2 = multiprocessing.Process(target=main)
    p3 = multiprocessing.Process(target=vsomeip_service)
    p4 = multiprocessing.Process(target=doip_service)

    processes.append(p1)
    processes.append(p2)
    processes.append(p3)
    processes.append(p4)

    for p in processes:
        p.start()

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("Main process interrupted. Terminating all processes...")
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=1.0)
                print(f"Process {p.name} terminated")
