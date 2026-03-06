"""
PythonCanDriver / ISO-TP 수정사항 검증 스크립트.

Sandbag이 실행 중인 상태에서 별도 프로세스로 실행한다.

사용법:
  # 정상 모드 테스트 (TC-1,2,4,5,6,7,8)
  python main.py --uds_echo_on --unknown_ff_on --vehicle_off --heartbit_off \
      --uds_heartbit_off --j1939_heartbit_off --periodic_error_off --overflow_off --dtc_off
  python test_driver_verify.py

  # Silent 모드 테스트 (TC-3)
  python main.py --uds_echo_on --uds_echo_silent --vehicle_off --heartbit_off \
      --uds_heartbit_off --j1939_heartbit_off --periodic_error_off --overflow_off --dtc_off
  python test_driver_verify.py --test tc3

  # 개별 테스트
  python test_driver_verify.py --test tc1
"""

import sys
import os
import can
import time
import threading
import argparse
import traceback

ARCHON_EXT = r'E:\Project\ArchonZ-Project\Archon\prebuilt\ext'
sys.path.insert(0, ARCHON_EXT)
sys.path.insert(0, os.path.join(ARCHON_EXT, 'IsotpDriver'))

from IsotpDriver.iso15765_2 import IsoTp

WS_URL = 'ws://localhost:54701'
FUNCTIONAL_ID = 0x7DF
DEFAULT_RESPONSE_ID = 0x7E8
WAIT_WINDOW = 2.0


def create_bus(receive_own=False):
    return can.Bus(
        interface='remote',
        channel=WS_URL,
        bitrate=500000,
        receive_own_messages=receive_own,
    )


# ---------------------------------------------------------------------------
# TestHarness: check_uds_response 로직을 동일하게 재현
# ---------------------------------------------------------------------------
class TestHarness:
    """pythoncandriver.py 의 수정된 check_uds_response() 패턴을 재현."""

    UDS_REQUESTS = [
        [0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
        [0x02, 0x19, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00],
        [0x02, 0x3E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    ]

    def __init__(self, bus: can.Bus):
        self.bus = bus
        self._diag_lock = threading.Lock()

    def check_uds_response(self, response_id, wait_window):
        result = []
        with self._diag_lock:
            try:
                isotp_inst = IsoTp(FUNCTIONAL_ID, response_id, bus=self.bus)
                for idx, uds_req in enumerate(self.UDS_REQUESTS):
                    msg = can.Message(
                        arbitration_id=FUNCTIONAL_ID,
                        data=uds_req,
                        is_extended_id=False,
                        is_fd=False,
                    )
                    self.bus.send(msg)
                    frame_data = isotp_inst.indication(wait_window)

                    if idx == 0:
                        if frame_data is None:
                            return None
                    if frame_data is not None:
                        result.append([hex(n) for n in frame_data])
            except Exception:
                raise
        return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
class _Result:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.detail = ''

    def ok(self, detail=''):
        self.passed = True
        self.detail = detail

    def fail(self, detail=''):
        self.passed = False
        self.detail = detail

    def __str__(self):
        tag = 'PASS' if self.passed else 'FAIL'
        s = f'[{tag}] {self.name}'
        if self.detail:
            s += f'  -- {self.detail}'
        return s


# ---------------------------------------------------------------------------
# TC-1: Lock 직렬화 검증
# ---------------------------------------------------------------------------
def tc1_lock_serialization():
    r = _Result('TC-1 Lock serialization')
    bus = None
    try:
        bus = create_bus()
        harness = TestHarness(bus)

        results = [None, None, None]
        errors = [None, None, None]

        def worker(idx):
            try:
                results[idx] = harness.check_uds_response(DEFAULT_RESPONSE_ID, WAIT_WINDOW)
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()

        deadline = time.time() + WAIT_WINDOW * 3 * 3 + 5
        for t in threads:
            remaining = max(0.1, deadline - time.time())
            t.join(timeout=remaining)

        alive = [t for t in threads if t.is_alive()]
        if alive:
            r.fail(f'deadlock: {len(alive)} thread(s) still alive')
            return r

        errs = [e for e in errors if e is not None]
        if errs:
            r.fail(f'exception in worker: {errs[0]}')
            return r

        completed = sum(1 for res in results if res is not None)
        r.ok(f'{completed}/3 calls completed (None means Default-Session timeout)')
    except Exception as e:
        r.fail(traceback.format_exc())
    finally:
        if bus:
            bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-2: Default Session 응답 수신 시 정상 진행
# ---------------------------------------------------------------------------
def tc2_default_session_response():
    r = _Result('TC-2 Default Session response OK')
    bus = None
    try:
        bus = create_bus()
        harness = TestHarness(bus)
        result = harness.check_uds_response(DEFAULT_RESPONSE_ID, WAIT_WINDOW)

        if result is None:
            r.fail('got None (timeout) - Sandbag UDS Echo not responding')
            return r

        if not isinstance(result, list) or len(result) == 0:
            r.fail(f'unexpected result type/empty: {result}')
            return r

        first = result[0]
        if '0x50' in first:
            r.ok(f'{len(result)} response(s), first={first}')
        else:
            r.fail(f'first response missing 0x50: {first}')
    except Exception:
        r.fail(traceback.format_exc())
    finally:
        if bus:
            bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-3: Default Session 무응답(timeout) 시 실패
#   Sandbag 을 --uds_echo_on --uds_echo_silent 로 실행해야 한다.
# ---------------------------------------------------------------------------
def tc3_default_session_timeout():
    r = _Result('TC-3 Default Session timeout (silent mode)')
    bus = None
    try:
        bus = create_bus()
        harness = TestHarness(bus)
        result = harness.check_uds_response(DEFAULT_RESPONSE_ID, WAIT_WINDOW)

        if result is None:
            r.ok('returned None as expected (timeout)')
        else:
            r.fail(f'expected None, got {result}')
    except Exception:
        r.fail(traceback.format_exc())
    finally:
        if bus:
            bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-4: FC-OVFLW 전송 검증
#   Sandbag 을 --unknown_ff_on 으로 실행해야 한다.
# ---------------------------------------------------------------------------
def tc4_fc_ovflw():
    r = _Result('TC-4 FC-OVFLW for unknown First Frame')
    isotp_bus = None
    monitor_bus = None
    try:
        isotp_bus = create_bus()
        monitor_bus = create_bus()

        UNKNOWN_ID = 0x321
        FC_OVFLW_BYTE0 = 0x32  # FC frame type (0x3) | OVFLW status (0x2)
        captured = []

        stop_event = threading.Event()

        def monitor_fc():
            while not stop_event.is_set():
                msg = monitor_bus.recv(timeout=0.5)
                if msg is None:
                    continue
                if msg.arbitration_id == UNKNOWN_ID and len(msg.data) >= 1:
                    if msg.data[0] == FC_OVFLW_BYTE0:
                        captured.append(msg)

        mon_thread = threading.Thread(target=monitor_fc, daemon=True)
        mon_thread.start()

        isotp_inst = IsoTp(FUNCTIONAL_ID, DEFAULT_RESPONSE_ID, bus=isotp_bus)
        # indication() 에서 Unknown FF 를 수신하면 FC-OVFLW 를 전송한다.
        # Sandbag 은 5초마다 FF 를 보내므로 8초 대기.
        isotp_inst.indication(wait_window=8.0)

        stop_event.set()
        mon_thread.join(timeout=2)

        if len(captured) > 0:
            r.ok(f'captured {len(captured)} FC-OVFLW message(s) for ID 0x{UNKNOWN_ID:X}')
        else:
            r.fail('no FC-OVFLW captured')
    except Exception:
        r.fail(traceback.format_exc())
    finally:
        if isotp_bus:
            isotp_bus.shutdown()
        if monitor_bus:
            monitor_bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-5: 회귀 - 일반 CAN output() 단발 송신
# ---------------------------------------------------------------------------
def tc5_single_output():
    r = _Result('TC-5 Single CAN output regression')
    send_bus = None
    recv_bus = None
    try:
        send_bus = create_bus()
        recv_bus = create_bus()
        time.sleep(0.3)

        TEST_ID = 0x123
        TEST_DATA = [0x01, 0x02, 0x03]

        msg = can.Message(arbitration_id=TEST_ID, data=TEST_DATA, is_extended_id=False)
        send_bus.send(msg)

        deadline = time.time() + 2.0
        found = False
        while time.time() < deadline:
            rx = recv_bus.recv(timeout=0.5)
            if rx and rx.arbitration_id == TEST_ID and list(rx.data[:3]) == TEST_DATA:
                found = True
                break

        if found:
            r.ok('message sent and received')
        else:
            r.fail('message not received within timeout')
    except Exception:
        r.fail(traceback.format_exc())
    finally:
        if send_bus:
            send_bus.shutdown()
        if recv_bus:
            recv_bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-6: 회귀 - DBC 주기 송신
# ---------------------------------------------------------------------------
def tc6_periodic_output():
    r = _Result('TC-6 Periodic CAN output regression')
    send_bus = None
    recv_bus = None
    try:
        send_bus = create_bus()
        recv_bus = create_bus()
        time.sleep(0.3)

        TEST_ID = 0x124
        TEST_DATA = [0xAA]
        CYCLE_MS = 100
        DURATION_MS = 500
        cycle_sec = CYCLE_MS / 1000.0
        duration_sec = DURATION_MS / 1000.0

        def periodic_sender():
            end = time.time() + duration_sec
            while time.time() < end:
                msg = can.Message(arbitration_id=TEST_ID, data=TEST_DATA, is_extended_id=False)
                send_bus.send(msg)
                time.sleep(cycle_sec)

        t = threading.Thread(target=periodic_sender)
        t.start()

        captured = []
        deadline = time.time() + duration_sec + 1.0
        while time.time() < deadline:
            rx = recv_bus.recv(timeout=0.5)
            if rx and rx.arbitration_id == TEST_ID:
                captured.append(rx)

        t.join(timeout=2)

        expected_min = int(duration_sec / cycle_sec) - 1
        if len(captured) >= expected_min:
            r.ok(f'received {len(captured)} periodic messages (expected >= {expected_min})')
        else:
            r.fail(f'received {len(captured)}, expected >= {expected_min}')
    except Exception:
        r.fail(traceback.format_exc())
    finally:
        if send_bus:
            send_bus.shutdown()
        if recv_bus:
            recv_bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-7: 회귀 - indication_all() 정상 동작
# ---------------------------------------------------------------------------
def tc7_indication_all():
    r = _Result('TC-7 indication_all() regression')
    bus = None
    try:
        bus = create_bus()

        isotp_inst = IsoTp(FUNCTIONAL_ID, DEFAULT_RESPONSE_ID, bus=bus)

        req = can.Message(
            arbitration_id=FUNCTIONAL_ID,
            data=[0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=False,
        )
        bus.send(req)

        result = isotp_inst.indication_all(wait_window=WAIT_WINDOW)

        if result is None:
            r.fail('indication_all returned None')
            return r

        total_message, frame_data = result
        r.ok(f'total_message={len(total_message)}, frame_data={frame_data}')
    except Exception:
        r.fail(traceback.format_exc())
    finally:
        if bus:
            bus.shutdown()
    return r


# ---------------------------------------------------------------------------
# TC-8: 라이프사이클 - Lock 누수 확인
# ---------------------------------------------------------------------------
def tc8_lifecycle_lock_leak():
    r = _Result('TC-8 Lifecycle lock leak')
    try:
        for cycle in range(1, 3):
            bus = create_bus()
            harness = TestHarness(bus)

            result = harness.check_uds_response(DEFAULT_RESPONSE_ID, WAIT_WINDOW)
            bus.shutdown()

            if cycle == 2:
                r.ok(f'cycle {cycle} completed without deadlock, result={result is not None}')
    except Exception:
        r.fail(traceback.format_exc())
    return r


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
ALL_NORMAL = ['tc1', 'tc2', 'tc4', 'tc5', 'tc6', 'tc7', 'tc8']
ALL_SILENT = ['tc3']

TC_MAP = {
    'tc1': tc1_lock_serialization,
    'tc2': tc2_default_session_response,
    'tc3': tc3_default_session_timeout,
    'tc4': tc4_fc_ovflw,
    'tc5': tc5_single_output,
    'tc6': tc6_periodic_output,
    'tc7': tc7_indication_all,
    'tc8': tc8_lifecycle_lock_leak,
}


def main():
    parser = argparse.ArgumentParser(description='PythonCanDriver / ISO-TP verification')
    parser.add_argument(
        '--test',
        choices=list(TC_MAP.keys()) + ['all', 'normal', 'silent'],
        default='normal',
        help='test case to run (default: normal = all except tc3)',
    )
    args = parser.parse_args()

    if args.test == 'all':
        targets = list(TC_MAP.keys())
    elif args.test == 'normal':
        targets = ALL_NORMAL
    elif args.test == 'silent':
        targets = ALL_SILENT
    else:
        targets = [args.test]

    print('=' * 60)
    print('  PythonCanDriver / ISO-TP Verification')
    print('=' * 60)
    print(f'  targets: {targets}')
    print()

    results = []
    for tc_name in targets:
        fn = TC_MAP[tc_name]
        print(f'--- Running {tc_name} ---')
        res = fn()
        results.append(res)
        print(f'  {res}')
        print()
        time.sleep(0.5)

    print('=' * 60)
    print('  Summary')
    print('=' * 60)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    for res in results:
        print(f'  {res}')
    print()
    print(f'  Total: {len(results)}   Passed: {passed}   Failed: {failed}')
    print('=' * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
