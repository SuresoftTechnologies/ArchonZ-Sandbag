# can-simulator

WSL2 환경에서 Docker 컨테이너 내부에서 Virtual CAN 인터페이스를 사용하기 위한 설정 도구입니다.
<br/><br/>

### 개요

Windows 환경에서 WSL2와 Docker를 활용하여 Virtual CAN 인터페이스를 구성하고, ICSim(Instrument Cluster Simulator)을 실행할 수 있는 환경을 제공합니다.

</br>

### 사전 요구사항

- Windows 10/11 환경
- WSL2 설치
- Docker Desktop for Windows 설치
- X11 서버 (Windows의 경우 VcXsrv 추천)

</br>

### 설치 및 사용 방법

**0. 이전 설정을 초기화합니다 (필요한 경우만)**

    a. wsl --unregister [배포판이름] (예: Ubuntu 또는 Ubuntu-22.04)

    b. Windows 프로그램 추가/제거에서 Ubuntu 선택 > 고급 옵션 > 초기화

    c. wsl --list --online 으로 설치할 배포판 이름 확인

    d. wsl --install -d [배포판이름]으로 재설치

**1. `setup-vcan.bat` 실행**

배치 파일은 다음 작업을 수행합니다:

- WSL에 모듈 설치
- .wslconfig 파일 설정
- WSL 재실행
- 필요한 CAN 모듈 로드

**2. Docker 이미지 빌드 및 컨테이너 실행:**

```bash
docker build -t [이미지이름] .
docker run [옵션] [이미지이름]

# 예시
docker build -t can-simulator .
docker run --cap-add=NET_ADMIN -p 54701:54701 --log-opt max-size=10m --log-opt max-file=3 --name=icsim_container can-simulator
```

컨테이너가 실행되면 Controller와 Simulator GUI가 자동으로 시작됩니다.

</br>

### 도커 컨테이너 실행 시 주요 옵션 설명

- `--cap-add=NET_ADMIN`: Virtual CAN 인터페이스 생성 및 설정에 필요한 권한 부여
- `-p port1:port2`: 포트 매핑 (port1: 호스트 시스템 포트, port2: 컨테이너 내부 포트)
- `--name`: 컨테이너 이름 지정 (선택 사항)
- `-e CAN_PORT=port -e CAN_BITRATE=bitrate`: CAN 포트와 비트레이트 설정 (기본값: 54701, 500000)
- `--log-opt`: 로그 로테이션 설정

📢 **중요**: `CAN_PORT` 환경변수는 `-p` 옵션의 두 번째 숫자와 동일해야 합니다.

</br>

### 프로젝트 구조

```
README.md
Dockerfile              # 빌드할 Docker file
setup-vcan.bat          # 커스텀 커널/모듈 자동 세팅을 위한 배치 파일
vmlinux                 # 빌드된 커스텀 커널 파일
kernel-modules/         # 모듈 파일들이 저장된 디렉토리
├── kernel/
│   ├── drivers/
│   │   └── net/
│   │       └── can/
│   │           └── vcan.ko
│   └── net/
│       └── can/
│           ├── can.ko
│           ├── can-raw.ko
│           └── can-bcm.ko
├── build
├── source
├── modules.alias
└── modules.dep
```

</br>

### 주의사항

- 이 프로젝트는 Virtual CAN을 사용하기 위해 WSL 커널을 수정합니다.
- 커스텀 커널 설정에 문제가 있는 경우 WSL 초기화가 필요할 수 있습니다.
- Docker와 WSL이 올바르게 설정되어 있어야 합니다.
