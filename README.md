# Test Environment for ArchonZ

Archon 에서 사용할 수 있는 테스트 환경 모음입니다.

## CAN Simulation

웹소켓으로 구성된 가상의 CAN Bus 에 대해 동작하는 다양한 가상의 태스크들을 설정하고 동작하는 구성입니다.
CAN Message 에 따라 DTC 에 문제를 보고하기도 하고, 동작이 제한되는등의 Fault 를 임의로 삽입하여 테스트 구성을 하기 위한 목적입니다.

### Remote CAN Bus

```
python -m can_remote --interface=virtual --channel=0 --bitrate=500000
```

### Run CAN Tasks

```
python main.py
```

## Trouble shooting

### python-OBD 

최신 버전 pint 를 사용하는 패키지가 pypi 에 없음, 수동 설치 필요

```
pip install git+https://github.com/brendan-w/python-OBD
```