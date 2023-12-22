# Test Environment for ArchonZ

Archon 에서 사용할 수 있는 테스트 환경 모음입니다.

## CAN Simulation

웹소켓으로 구성된 가상의 CAN Bus 에 대해 동작하는 다양한 가상의 태스크들을 설정하고 동작하는 구성입니다.
CAN Message 에 따라 DTC 에 문제를 보고하기도 하고, 동작이 제한되는등의 Fault 를 임의로 삽입하여 테스트 구성을 하기 위한 목적입니다.

### Remote CAN Bus

```
python -m can_remote --interface=virtual --channel=0 --bitrate=500000
```

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