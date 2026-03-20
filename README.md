# Test Environment for ArchonZ

Archon 에서 사용할 수 있는 테스트 환경 모음입니다.

## CAN Simulation

웹소켓으로 구성된 가상의 CAN Bus 에 대해 동작하는 다양한 가상의 태스크들을 설정하고 동작하는 구성입니다.
CAN Message 에 따라 DTC 에 문제를 보고하기도 하고, 동작이 제한되는등의 Fault 를 임의로 삽입하여 테스트 구성을 하기 위한 목적입니다.


### Remote CAN Bus

```
python -m can_remote --interface=virtual --channel=0 --bitrate=500000
```

### UDS Demo with CVE-2024-51073
데모 시나리오:
1. 특정 uds 서비스의 특정 데이터가 송신됨  
(AV= TestCommunicationControl.Request.SendCommunicationControl.Size.ScalarVariance.9)
2. sandbag 의 모든 can 관련 task 가 정지하면서 메시지가 송신되지 않음
3. weakness 가 잡힘 (critical)
4. connection test 로 sandbag 의 정지된 task 를 재개할 수 있음

sandbag 실행 시, can_demo_on 옵션을 통해 데모 시나리오를 수행할 수 있음
```
python main.py --can_demo_on [option]

option list and default value:
--stop_id       : 0x7c6
--stop_payload  : "09 28 00 00 AA AA AA AA" 
--resume_id     : 0x7c6
--resume_payload: "01 10 00 AA AA AA AA AA"
```
(ref. https://github.com/nitinronge91/KIA-SELTOS-Cluster-Vulnerabilities/blob/3755e3f692dce5b1ab06de2d04a2433c907ab21c/CVE/Control%20CAN%20communication%20for%20KIA%20SELTOS%20Cluster%20CVE-2024-51073.md) 

### SimVA CAN

SimVA 용 CANBus 를 python-can 의 확장요소로 다운로드 받아야 합니다. 
```
pip install git+https://github.com/minhyuk/simva-can.git
```

SimVA 와 연동 요소의 방해를 없애기 위해 기본적으로 설정된 가상 신호들을 모두 Off 합니다.
```
python main.py --overflow_off --vehicle_off --dtc_off --periodic_error_off --heartbit_off
```

SimVA 에서 설정한 송/수신 채널을 CAN Remote 로 Redirect 하는 유틸리티를 실행합니다.
이제 CAN Remote 에서 SimVA 의 송수신을 확인할 수 있습니다. 여기에 퍼징도 가능합니다.
```
python simva_redirect.py --channel [no]
```

### 기본 CAN 태스크 DTC 응답

아래 태스크들은 기본적으로 활성화되어 있으며, OBD-II Mode `0x03` (Read Stored DTCs) 요청(`0x7DF`) 수신 시 `0x7E8` 로 DTC를 응답합니다.

| 태스크 | 비활성화 옵션 | 응답 DTC | 비고 |
|---|---|---|---|
| Diagnostic Control | `--dtc_off` | **U3FFF** (`0xFFFF`) | `0xD0C` 수신 → `0xD1C` 에코 응답도 포함 |
| Throttle Control | `--vehicle_off` | **U3FFF** (`0xFFFF`) | ECU Reset (`0x11 0x01`) 시 속도/RPM 초기화 후 재기동 |

### UDS Echo (ECU Simulator)

CAN 버스 위에서 실제 ECU처럼 UDS/OBD-II 요청에 응답하는 시뮬레이터입니다.
`--uds_echo_on` 옵션으로 활성화합니다.

```
python main.py --uds_echo_on [option]

option list and default value:
--response_id     : 0x7E8              # UDS 응답 Arbitration ID
--uds_echo_silent : (flag)             # 0x10 DiagnosticSessionControl 무응답 모드
--vin             : WAUZZZ8V9FA149850  # VIN 문자열 (17자)
```

#### CAN ID 구성

| 구분 | ID | 설명 |
|---|---|---|
| Request | `0x7DF` | OBD-II 기능 주소 (broadcast) |
| Request | `0x7E0` ~ `0x7E7` | OBD-II 물리 주소 범위 |
| Request | `0x7EE` | Archon 전용 요청 |
| Request | `0x7FF` | 추가 요청 ID |
| Response | `0x7E8` | 기본 응답 ID (`--response_id` 로 변경 가능) |

#### 지원 서비스

**OBD-II**

| SID | 서비스 | 응답 내용 |
|---|---|---|
| `0x01` | Show Current Data | PID 별 센서 값 (냉각수 온도, RPM, 속도 등) |
| `0x02` | Show Freeze Frame | 고정 프레임 데이터 |
| `0x03` | Read Stored DTCs | **P0100** (MAF Circuit Malfunction), **P0102** (MAF Circuit Low Input) |
| `0x04` | Clear DTCs | 정상 응답 |
| `0x07` | Read Pending DTCs | 보류 DTC |
| `0x09` | Vehicle Information | VIN (`0x02`), ECU Name (`0x0A`) |
| `0x0A` | Read Permanent DTCs | 영구 DTC 0건 |

**UDS**

| SID | 서비스 | 응답 내용 |
|---|---|---|
| `0x10` | DiagnosticSessionControl | 세션 전환 (`0x01`~`0x04`), silent 모드 시 무응답 |
| `0x11` | ECUReset | 리셋 후 세션/보안 초기화 |
| `0x14` | ClearDiagnosticInformation | 정상 응답 |
| `0x19` | ReadDTCInformation | sub `0x01`: DTC 2건 보고, sub `0x02`/`0x0A`: DTC `0x01002F` |
| `0x22` | ReadDataByIdentifier | `F190`=VIN, `F187`=부품번호, `F189`=SW버전, `F191`=HW번호, `F19E`=ECU명 |
| `0x27` | SecurityAccess | Seed 요청 → 랜덤 시드, Key 전송 → 항상 승인 |
| `0x28` | CommunicationControl | sub-function `0x00`~`0x03` 정상 응답 |
| `0x2E` | WriteDataByIdentifier | 정상 응답 |
| `0x31` | RoutineControl | 정상 응답 |
| `0x3E` | TesterPresent | 정상 응답 |
| `0x85` | ControlDTCSettings | On/Off (`0x01`/`0x02`) 정상 응답 |

미지원 SID 수신 시 NRC `0x11` (serviceNotSupported) 로 응답합니다.
ISO-TP Single Frame / Multi Frame (FF+CF) 송수신을 모두 지원합니다.

#### 옵션 충돌 주의

`--uds_echo_on` 사용 시 아래 태스크들과 CAN ID가 충돌하므로, 반드시 해당 태스크를 비활성화해야 합니다.

| 충돌 태스크 | 비활성화 옵션 | 충돌 원인 |
|---|---|---|
| Throttle Control | `--vehicle_off` | `0x7DF` 수신 + `0x7E8` 응답이 UDS Echo와 동일하여 OBD 요청 시 이중 응답 발생 (Mode `0x01`, `0x03`, SID `0x11`) |
| HeartBit | `--heartbit_off` | `0x7DF`, `0x7FF`, `0x7E0` 으로 주기적 메시지를 전송하여 UDS Echo가 불필요한 응답을 지속 생성 |

권장 실행 예시:
```
python main.py --uds_echo_on --vehicle_off --heartbit_off
```

아래 태스크는 직접적인 ID 충돌은 없으나, 혼용 시 의도와 다르게 동작할 수 있습니다.

| 태스크 | 옵션 | 비고 |
|---|---|---|
| CAN Demo (CVE 시나리오) | `--can_demo_on` | Stop Controller 가 전체 태스크를 정지시키므로 UDS Echo 도 함께 중단됨 |

### Run CAN Tasks & SOME/IP Server & DoIP Server

```
python main.py
```

### DoIP Server Virtual ECU Configuration

DoIP Server를 참고한 오픈소스는 다음과 같습니다:
https://gitlab.com/rohfle/doip-simulator

가상 ECU의 설정 정보는 다음과 같습니다.

- VIN = TESTVIN0000012345
- EID = 12-34-56-78-9A-BC
- Logical Address = [ 0x3300, 0x3301 ]

```
config = {
    'vin': 'TESTVIN0000012345',
    'mac': int('123456789ABC', 16),
    'addresses': {
        'discovery': 0x3000,
        'server': 0x3010,
    },
    'datamap': {
        0x3300: {
            0x3200: ('Dummy Accelerator', framp(0xff, 2, 0), accelerator_format),
            0x3230: ('Dummy Brake', framp(0x5000, 10, 0), brakehydralic_format),
        },
        0x3301: {
            0x3250: ('Dummy Steering', fsine(0x7fff, 4, 0), steeringangle_format),
        }
    }
}
```

## Trouble shooting

### python-OBD 

최신 버전 pint 를 사용하는 패키지가 pypi 에 없음, 수동 설치 필요

```
pip install git+https://github.com/brendan-w/python-OBD
```
