"""
UDS/OBD-II ECU Simulator — ported from zombieCraig/uds-server (GPLv2).

Sandbag engine.Task 로 통합되어 CAN 버스 위에서 ECU 응답을 에뮬레이션한다.
ISO-TP single-frame / multi-frame 응답을 모두 지원하며,
silent_mode 를 통해 특정 서비스의 무응답(timeout) 시나리오도 재현할 수 있다.

지원 서비스:
  OBD-II  : 0x01  0x02  0x03  0x04  0x07  0x09  0x0A
  UDS     : 0x10  0x11  0x14  0x19  0x22  0x27  0x28
            0x2E  0x31  0x3E  0x85
"""

from typing import Any
from typing_extensions import override
from can import Bus, Message
import engine
import random

# ---------------------------------------------------------------------------
# ISO-TP constants
# ---------------------------------------------------------------------------
SF_FRAME_ID = 0
FF_FRAME_ID = 1
CF_FRAME_ID = 2
FC_FRAME_ID = 3

# ---------------------------------------------------------------------------
# NRC (Negative Response Codes)
# ---------------------------------------------------------------------------
NRC_SUB_FUNCTION_NOT_SUPPORTED = 0x12
NRC_INCORRECT_MSG_LENGTH = 0x13
NRC_CONDITIONS_NOT_CORRECT = 0x22
NRC_REQUEST_OUT_OF_RANGE = 0x31
NRC_SECURITY_ACCESS_DENIED = 0x33
NRC_INVALID_KEY = 0x35
NRC_SERVICE_NOT_SUPPORTED = 0x11
NRC_SERVICE_NOT_SUPPORTED_IN_SESSION = 0x7F


class Task_UDS_Echo(engine.Task):
    """
    zombieCraig/uds-server 의 핵심 OBD/UDS 응답 로직을 Python 으로 포팅한 ECU 시뮬레이터.

    Parameters
    ----------
    response_id : int
        UDS/OBD 응답에 사용할 CAN Arbitration ID (기본 0x7E8).
    request_ids : list[int]
        수신 감시할 요청 ID 목록 (기본 [0x7DF, 0x7E0]).
    silent_mode : bool
        True 이면 DiagnosticSessionControl(0x10) 에 무응답.
    vin : str
        VIN 문자열 (기본 17자).
    """

    # 0x7DF = OBD-II functional, 0x7E0~0x7E7 = OBD-II physical,
    # 0x7EE = Archon request, 0x7FF = 추가 요청 ID.
    # 0xEEE 제외(Throttle이 전송해 UDS가 아님)
    DEFAULT_REQUEST_IDS = [0x7DF, *range(0x7E0, 0x7E8), 0x7EE, 0x7FF]

    def __init__(
        self,
        response_id=0x7E8,
        silent_mode=False,
        request_ids=None,
        vin="WAUZZZ8V9FA149850",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._name = "uds_echo"
        self.response_id = response_id
        self.request_ids = request_ids or self.DEFAULT_REQUEST_IDS
        self.silent_mode = silent_mode
        self.vin = vin

        # ECU state
        self._session = 0x01  # default session
        self._security_unlocked = False

        # ISO-TP multi-frame TX buffer
        self._mf_buffer: list[int] = []
        self._mf_seq = 0
        # ISO-TP multi-frame RX reassembly (tester → ECU)
        self._rx_mf_pending: list[int] | None = None
        self._rx_mf_total: int = 0
        self._rx_mf_req_id: int = 0

    # ------------------------------------------------------------------
    # engine.Task overrides
    # ------------------------------------------------------------------
    @override
    def on_message_received(self, msg: Message):
        try:
            if not msg.data or len(msg.data) == 0:
                return

            # Flow-control from tester → push remaining multi-frame data
            if msg.arbitration_id in self.request_ids:
                if (msg.data[0] >> 4) & 0xF == FC_FRAME_ID and self._mf_buffer:
                    self._push_consecutive_frames()
                    return

            if msg.arbitration_id not in self.request_ids:
                return
            if len(msg.data) < 2:
                return

            pci = msg.data[0]
            frame_type = (pci >> 4) & 0xF

            # First Frame: start reassembly
            if frame_type == FF_FRAME_ID and len(msg.data) >= 2:
                self._rx_mf_total = ((msg.data[0] & 0x0F) << 8) | msg.data[1]
                self._rx_mf_pending = list(msg.data[2:8])
                self._rx_mf_req_id = msg.arbitration_id
                if len(self._rx_mf_pending) >= self._rx_mf_total:
                    self._dispatch_reassembled()
                return

            # Consecutive Frame: continue reassembly
            if frame_type == CF_FRAME_ID and self._rx_mf_pending is not None:
                self._rx_mf_pending.extend(msg.data[1:8])
                if len(self._rx_mf_pending) >= self._rx_mf_total:
                    self._dispatch_reassembled()
                return

            # Single frame
            if frame_type != SF_FRAME_ID:
                return
            sf_dl = pci & 0xF
            if sf_dl < 1 or len(msg.data) < sf_dl + 1:
                return

            sid = msg.data[1]
            self._dispatch(sid, msg)
        except Exception:
            pass

    def _dispatch_reassembled(self):
        """Dispatch reassembled multi-frame request and clear RX state."""
        if self._rx_mf_pending is None or len(self._rx_mf_pending) < self._rx_mf_total:
            return
        payload = self._rx_mf_pending[: self._rx_mf_total]
        req_id = self._rx_mf_req_id
        self._rx_mf_pending = None
        self._rx_mf_total = 0
        self._rx_mf_req_id = 0
        if len(payload) < 2:
            return
        # data[0]=length, data[1]=SID (SF-shaped for _dispatch)
        data = [len(payload) & 0x0F] + payload
        synthetic = Message(
            arbitration_id=req_id, data=bytes(data), is_extended_id=False
        )
        self._dispatch(payload[0], synthetic)

    @override
    def get_data(self):
        return None, None

    @override
    def run(self, bus: Bus):
        return super().run(bus)

    @override
    def is_fd(self):
        return True

    # ------------------------------------------------------------------
    # ISO-TP helpers
    # ------------------------------------------------------------------
    def _isotp_send(self, payload: list[int]):
        """ISO-TP 응답 전송. single-frame 이면 바로, multi-frame 이면 FF+CF."""
        size = len(payload)
        if size <= 7:
            frame = [size] + payload + [0x00] * (7 - size)
            self.send(self.response_id, frame)
        else:
            # First Frame
            ff = [0x10 | ((size >> 8) & 0x0F), size & 0xFF] + payload[:6]
            self.send(self.response_id, ff)
            self._mf_buffer = payload[6:]
            self._mf_seq = 0x21

    def _push_consecutive_frames(self):
        """FC 수신 후 남은 Consecutive Frame 전송."""
        while self._mf_buffer:
            chunk = self._mf_buffer[:7]
            self._mf_buffer = self._mf_buffer[7:]
            cf = [self._mf_seq] + chunk
            if len(cf) < 8:
                cf += [0x00] * (8 - len(cf))
            self.send(self.response_id, cf)
            self._mf_seq = ((self._mf_seq & 0x0F) + 1) % 16 | 0x20

    def _send_positive(self, sid: int, data: list[int]):
        self._isotp_send([sid + 0x40] + data)

    def _send_nrc(self, sid: int, nrc: int):
        self._isotp_send([0x7F, sid, nrc])

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------
    def _dispatch(self, sid: int, msg: Message):
        handlers = {
            # OBD-II
            0x01: self._handle_obd_current_data,
            0x02: self._handle_obd_freeze_frame,
            0x03: self._handle_obd_stored_dtc,
            0x04: self._handle_obd_clear_dtc,
            0x07: self._handle_obd_pending_dtc,
            0x09: self._handle_obd_vehicle_info,
            0x0A: self._handle_obd_perm_dtc,
            # UDS
            0x10: self._handle_diagnostic_session_control,
            0x11: self._handle_ecu_reset,
            0x14: self._handle_clear_dtc,
            0x19: self._handle_read_dtc_info,
            0x22: self._handle_read_data_by_id,
            0x27: self._handle_security_access,
            0x28: self._handle_communication_control,
            0x2E: self._handle_write_data_by_id,
            0x31: self._handle_routine_control,
            0x3E: self._handle_tester_present,
            0x85: self._handle_control_dtc_settings,
        }
        handler = handlers.get(sid)
        if handler:
            handler(msg)
        else:
            self._send_nrc(sid, NRC_SERVICE_NOT_SUPPORTED)

    # ==================================================================
    # OBD-II Service Handlers (ported from uds-server.c)
    # ==================================================================

    def _handle_obd_current_data(self, msg: Message):
        """Mode 0x01 — Show Current Data."""
        pid = msg.data[2] if len(msg.data) > 2 else 0x00
        sid = 0x01
        if pid in (0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0):
            self._send_positive(sid, [pid, 0xBF, 0xBF, 0xB9, 0x93])
        elif pid == 0x01:
            # MIL off, 0 DTCs, tests supported
            self._send_positive(sid, [pid, 0x00, 0x07, 0xE5, 0xE5])
        elif pid == 0x05:
            # Engine coolant temp: 80°C → value = 80+40 = 120
            self._send_positive(sid, [pid, 120])
        elif pid == 0x0C:
            # RPM: 3000 rpm → value = 3000*4 = 12000 → 0x2EE0
            self._send_positive(sid, [pid, 0x2E, 0xE0])
        elif pid == 0x0D:
            # Vehicle speed: 60 km/h
            self._send_positive(sid, [pid, 60])
        elif pid == 0x2F:
            # Fuel tank level: 70%  → value = 70*255/100 ≈ 178
            self._send_positive(sid, [pid, 178])
        elif pid == 0x41:
            # Monitor status
            self._send_positive(sid, [pid, 0x00, 0x0F, 0xFF, 0x00])
        elif pid == 0x51:
            # Fuel type: gasoline = 1
            self._send_positive(sid, [pid, 0x01])
        else:
            self._send_positive(sid, [pid, 0x00])

    def _handle_obd_freeze_frame(self, msg: Message):
        """Mode 0x02 — Show Freeze Frame."""
        self._send_positive(0x02, [0x01, 0x01])

    def _handle_obd_stored_dtc(self, msg: Message):
        """Mode 0x03 — Read Stored DTCs (2 DTCs)."""
        self._send_positive(0x03, [0x02, 0x01, 0x00, 0x01, 0x02])

    def _handle_obd_clear_dtc(self, msg: Message):
        """Mode 0x04 — Clear DTCs."""
        self._send_positive(0x04, [])

    def _handle_obd_pending_dtc(self, msg: Message):
        """Mode 0x07 — Read Pending DTCs."""
        self._send_positive(0x07, [0x01, 0x02, 0x03])

    def _handle_obd_vehicle_info(self, msg: Message):
        """Mode 0x09 — Vehicle Information (VIN, ECU name)."""
        pid = msg.data[2] if len(msg.data) > 2 else 0x00
        sid = 0x09
        if pid == 0x00:
            # Supported info PIDs
            self._send_positive(sid, [pid, 0x55, 0x00, 0x00, 0x00])
        elif pid == 0x02:
            # VIN (multi-frame via ISO-TP)
            vin_bytes = [ord(c) for c in self.vin]
            self._send_positive(sid, [pid, 0x01] + vin_bytes)
        elif pid == 0x0A:
            # ECU name
            name_bytes = [ord(c) for c in "ARCHONZ_ECU"]
            self._send_positive(sid, [pid, 0x01] + name_bytes)
        else:
            self._send_positive(sid, [pid, 0x00])

    def _handle_obd_perm_dtc(self, msg: Message):
        """Mode 0x0A — Read Permanent DTCs (0 DTCs)."""
        self._send_positive(0x0A, [0x00])

    # ==================================================================
    # UDS Service Handlers (ported from uds-server.c)
    # ==================================================================

    def _handle_diagnostic_session_control(self, msg: Message):
        """SID 0x10 — DiagnosticSessionControl."""
        if self.silent_mode:
            return
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x01
        if sub_fn in (0x01, 0x02, 0x03, 0x04):
            self._session = sub_fn
            # P2 server timing: 0x0032 (50ms), P2* timing: 0x01F4 (500ms)
            self._send_positive(0x10, [sub_fn, 0x00, 0x32, 0x01, 0xF4])
        else:
            self._send_nrc(0x10, NRC_SUB_FUNCTION_NOT_SUPPORTED)

    def _handle_ecu_reset(self, msg: Message):
        """SID 0x11 — ECUReset."""
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x01
        if sub_fn in (0x01, 0x02, 0x03):
            self._session = 0x01
            self._security_unlocked = False
            self._send_positive(0x11, [sub_fn, 0x0F])
        elif sub_fn in (0x04, 0x05):
            self._send_positive(0x11, [sub_fn])
        else:
            self._send_nrc(0x11, NRC_SUB_FUNCTION_NOT_SUPPORTED)

    def _handle_clear_dtc(self, msg: Message):
        """SID 0x14 — ClearDiagnosticInformation."""
        self._send_positive(0x14, [])

    def _handle_read_dtc_info(self, msg: Message):
        """SID 0x19 — ReadDTCInformation."""
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x01
        if sub_fn == 0x01:
            # reportNumberOfDTCByStatusMask
            mask = msg.data[3] if len(msg.data) > 3 else 0xFF
            self._send_positive(0x19, [sub_fn, 0xFF, 0x00, 0x02])
        elif sub_fn == 0x02:
            # reportDTCByStatusMask — 1 DTC (keep ≤7 bytes for single-frame)
            mask = msg.data[3] if len(msg.data) > 3 else 0xFF
            self._send_positive(0x19, [sub_fn, mask, 0x01, 0x00, 0x2F])
        elif sub_fn == 0x06:
            # reportDTCExtDataRecordByDTCNumber
            self._send_positive(0x19, [sub_fn, 0x00])
        elif sub_fn == 0x0A:
            # reportSupportedDTC (keep ≤7 bytes for single-frame)
            self._send_positive(0x19, [sub_fn, 0xFF, 0x01, 0x00, 0x2F])
        else:
            self._send_nrc(0x19, NRC_SUB_FUNCTION_NOT_SUPPORTED)

    def _handle_read_data_by_id(self, msg: Message):
        """SID 0x22 — ReadDataByIdentifier."""
        if len(msg.data) < 4:
            self._send_nrc(0x22, NRC_INCORRECT_MSG_LENGTH)
            return
        did_hi = msg.data[2]
        did_lo = msg.data[3]
        did = (did_hi << 8) | did_lo

        if did == 0xF190:
            # VIN
            vin_bytes = [ord(c) for c in self.vin]
            self._send_positive(0x22, [did_hi, did_lo] + vin_bytes)
        elif did == 0xF187:
            # Spare part number
            part = [0x30, 0x34, 0x45, 0x39, 0x30, 0x36, 0x33, 0x32, 0x33, 0x46, 0x20]
            self._send_positive(0x22, [did_hi, did_lo] + part)
        elif did == 0xF189:
            # Software version
            self._send_positive(0x22, [did_hi, did_lo, 0x38, 0x34, 0x31, 0x30])
        elif did == 0xF191:
            # ECU HW number
            self._send_positive(0x22, [did_hi, did_lo, 0x48, 0x57, 0x30, 0x31])
        elif did == 0xF19E:
            # ASAM/ODX name
            name = [ord(c) for c in "ArchonZ_ECU"]
            self._send_positive(0x22, [did_hi, did_lo] + name)
        else:
            self._send_nrc(0x22, NRC_REQUEST_OUT_OF_RANGE)

    def _handle_security_access(self, msg: Message):
        """SID 0x27 — SecurityAccess."""
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x01
        if sub_fn % 2 == 1:
            # Request Seed (odd sub-function)
            seed = [random.randint(0, 0xFF) for _ in range(4)]
            self._send_positive(0x27, [sub_fn] + seed)
        elif sub_fn % 2 == 0:
            # Send Key (even sub-function) — always accept
            self._security_unlocked = True
            self._send_positive(0x27, [sub_fn])
        else:
            self._send_nrc(0x27, NRC_SUB_FUNCTION_NOT_SUPPORTED)

    def _handle_communication_control(self, msg: Message):
        """SID 0x28 — CommunicationControl."""
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x00
        if sub_fn in (0x00, 0x01, 0x02, 0x03):
            self._send_positive(0x28, [sub_fn])
        else:
            self._send_nrc(0x28, NRC_SUB_FUNCTION_NOT_SUPPORTED)

    def _handle_write_data_by_id(self, msg: Message):
        """SID 0x2E — WriteDataByIdentifier."""
        if len(msg.data) < 4:
            self._send_nrc(0x2E, NRC_INCORRECT_MSG_LENGTH)
            return
        did_hi = msg.data[2]
        did_lo = msg.data[3]
        self._send_positive(0x2E, [did_hi, did_lo])

    def _handle_routine_control(self, msg: Message):
        """SID 0x31 — RoutineControl."""
        if len(msg.data) < 4:
            self._send_nrc(0x31, NRC_INCORRECT_MSG_LENGTH)
            return
        sub_fn = msg.data[2]
        rid_hi = msg.data[3]
        rid_lo = msg.data[4] if len(msg.data) > 4 else 0x00
        self._send_positive(0x31, [sub_fn, rid_hi, rid_lo])

    def _handle_tester_present(self, msg: Message):
        """SID 0x3E — TesterPresent."""
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x00
        self._send_positive(0x3E, [sub_fn])

    def _handle_control_dtc_settings(self, msg: Message):
        """SID 0x85 — ControlDTCSettings."""
        sub_fn = msg.data[2] if len(msg.data) > 2 else 0x01
        if sub_fn in (0x01, 0x02):
            self._send_positive(0x85, [sub_fn])
        else:
            self._send_nrc(0x85, NRC_SUB_FUNCTION_NOT_SUPPORTED)
