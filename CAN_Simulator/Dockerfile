FROM ubuntu:20.04

# GUI 애플리케이션 실행에 필요한 환경변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=host.docker.internal:0.0
ENV SDL_VIDEODRIVER=x11
ENV XDG_RUNTIME_DIR=/tmp/runtime-dir

# 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libsdl2-dev \
    libsdl2-image-dev \
    can-utils \
    net-tools \
    iproute2 \
    python3 \
    python3-pip

# 정확한 버전의 Python 패키지 설치
RUN pip3 install msgpack==1.0.8 \
    packaging==25.0 \
    python-can==4.2.1 \
    python-can-remote==0.2.2 \
    typing_extensions==4.13.2 \
    websocket-client==1.8.0 \
    wrapt==1.17.2

# 작업 디렉토리 설정
WORKDIR /app

# ICSim 소스 다운로드
RUN git clone https://github.com/zombieCraig/ICSim.git

# ICSim 빌드
WORKDIR /app/ICSim
RUN make

# 런타임 디렉토리 생성
RUN mkdir -p /tmp/runtime-dir && chmod 700 /tmp/runtime-dir

# 로그 저장 스크립트 생성
RUN echo '#!/bin/bash\n\
# 로그 파일 이름 생성\n\
LOG_FILE="/app/ICSim/candump-$(date +%Y-%m-%d_%H%M%S).log"\n\
\n\
echo "================================================="\n\
echo "CAN 메시지 로깅을 시작합니다..."\n\
echo "로그 파일: $LOG_FILE"\n\
echo "로깅을 중지하려면 Ctrl+C를 누르세요"\n\
echo "================================================="\n\
\n\
# 올바른 candump 로그 저장 명령어\n\d
candump -l vcan0\n\
\n\
echo "================================================="\n\
echo "CAN 메시지 로깅이 완료되었습니다."\n\
echo "로그가 저장되었습니다."\n\
echo "호스트로 복사하려면:"\n\
echo "docker cp [컨테이너이름]:/app/ICSim/[로그파일명] [원하는경로]"\n\
echo "================================================="\n\
' > /app/save_log.sh && chmod +x /app/save_log.sh

RUN echo '#!/bin/bash\n\
# ICSim 컨트롤러 재시작\n\
cd /app/ICSim\n\
ls\n\
echo "인터페이스 상태:"\n\
ip link show vcan0\n\
./controls vcan0 &\n\
CONTROLS_PID=$!\n\
echo "ICSim 컨트롤러가 재시작되었습니다.(PID: $CONTROLS_PID)"\n\
# 프로세스가 살아있는지 계속 확인\n\
while true; do\n\
    sleep 5\n\
    # controller 프로세스 상태 확인\n\
    if ! ps -p $CONTROLS_PID > /dev/null; then\n\
        echo "컨테이너 프로세스가 종료되었습니다. 컨테이너를 재시작합니다."\n\
        ./controls vcan0 &\n\
        echo "ICSim 컨트롤러가 재시작되었습니다.(PID: $CONTROLS_PID)"\n\
        exit 1\n\
    fi\n\
done\n\
' > /app/controller_restart.sh && chmod +x /app/controller_restart.sh

# 가상 CAN 인터페이스 설정 및 시작 스크립트 생성
RUN echo '#!/bin/bash\n\
# 환경 변수에서 값을 읽거나 기본값 사용\n\
PORT=${CAN_PORT:-54701}\n\
BITRATE=${CAN_BITRATE:-500000}\n\
\n\
echo "CAN 서버를 포트 $PORT, bitrate $BITRATE으로 시작합니다."\n\
\n\
ip link add dev vcan0 type vcan || echo "vcan0 인터페이스가 이미 존재할 수 있습니다."\n\
ip link set up vcan0\n\
echo "Virtual CAN 인터페이스(vcan0)가 설정되었습니다."\n\
echo "인터페이스 상태:"\n\
ip link show vcan0\n\
\n\
# Remote CAN 서버 백그라운드로 시작\n\
python3 -m can_remote -i socketcan -c vcan0 -p $PORT -b $BITRATE -vv &\n\
REMOTE_PID=$!\n\
echo "Remote CAN 서버가 시작되었습니다.(PID: $REMOTE_PID, 포트: $PORT, Bitrate: $BITRATE)"\n\
\n\
# ICSim 시뮬레이터 시작\n\
cd /app/ICSim\n\
./icsim vcan0 &\n\
ICSIM_PID=$!\n\
echo "ICSim 시뮬레이터가 시작되었습니다.(PID: $ICSIM_PID)"\n\
\n\
# ICSim 컨트롤러 시작\n\
./controls vcan0 &\n\
CONTROLS_PID=$!\n\
echo "ICSim 컨트롤러가 시작되었습니다.(PID: $CONTROLS_PID)"\n\
\n\
echo "================================================="\n\
echo "모든 서비스가 시작되었습니다."\n\
echo "ICSim 시뮬레이터와 컨트롤러가 실행 중입니다."\n\
echo "================================================="\n\
echo "로그를 저장하려면:"\n\
echo "docker exec -it [컨테이너이름] /app/save_log.sh"\n\
echo "(로그 저장을 중지하려면 Ctrl+C를 누르세요)"\n\
echo "================================================="\n\
echo "컨트롤러를 재시작하려면:"\n\
echo "docker exec -it [컨테이너이름] /app/controller_restart.sh"\n\
echo "컨트롤러를 종료하려면 해당 gui를 종료하세요"\n\
echo "================================================="\n\
echo "[컨테이너이름]을 확인하려면:"\n\
echo "docker ps"\n\
echo "================================================="\n\
\n\
# 종료 시그널을 받으면 모든 프로세스 종료\n\
trap "kill $REMOTE_PID $ICSIM_PID $CONTROLS_PID; exit" SIGINT SIGTERM\n\
\n\
# 프로세스가 모두 살아있는지 계속 확인\n\
while true; do\n\
    sleep 5\n\
    # controller 제외 주요 프로세스 상태 확인\n\
    if ! ps -p $REMOTE_PID > /dev/null || ! ps -p $ICSIM_PID > /dev/null; then\n\
        echo "일부 프로세스가 종료되었습니다. 컨테이너를 종료합니다."\n\
        echo "x11 서버가 켜져있는지 확인해주세요."\n\
        exit 1\n\
    fi\n\
done\n\
' > /app/start.sh && chmod +x /app/start.sh

# 포트 노출
EXPOSE ${CAN_PORT}

# 컨테이너 시작 시 스크립트 실행
CMD ["/bin/bash", "/app/start.sh"]