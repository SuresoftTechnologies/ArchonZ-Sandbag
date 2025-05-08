@echo off
echo WSL Virtual CAN Setup
echo ===================
REM 현재 디렉토리 경로 확인
set CURRENT_DIR=%~dp0
echo Setup directory: %CURRENT_DIR%


REM WSL 실행 중인지 확인 / 설치된 WSL 배포판 목록 출력
echo .
echo Available WSL distributions:
wsl -l -v
if %ERRORLEVEL% NEQ 0 (
    echo WSL is not available. Please check WSL installation.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo .

REM 사용자로부터 WSL 배포판 이름 입력 받기
set /p WSL_DISTRO="Enter the name of the WSL distribution to use: "

REM 입력받은 배포판이 존재하는지 확인
wsl -d %WSL_DISTRO% -e echo "Testing connection to %WSL_DISTRO%..."
if %ERRORLEVEL% NEQ 0 (
    echo Could not connect to distribution "%WSL_DISTRO%". Please check the name and try again.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo Using WSL distribution: %WSL_DISTRO%

REM sudo 권한 유지 설정 (NOPASSWD)
echo Setting up passwordless sudo for this session...
wsl -d %WSL_DISTRO% -e bash -c "echo '%%sudo ALL=(ALL) NOPASSWD: ALL' | sudo EDITOR='tee -a' visudo"

REM 고정된 커널 버전 사용
set KERNEL_VERSION=5.15.167.4-microsoft-standard-WSL2+
echo Using kernel version: %KERNEL_VERSION%

REM .wslconfig 파일 생성 (커스텀 커널 지정)
echo Creating .wslconfig file...
echo [wsl2] > "%USERPROFILE%\.wslconfig"
set KERNEL_PATH=%CURRENT_DIR:\=\\%
echo kernel=%KERNEL_PATH%vmlinux >> "%USERPROFILE%\.wslconfig"

REM 모듈 디렉토리 생성 및 복사
echo Copying kernel modules to WSL...

REM Windows 경로를 WSL 경로로 변환
echo Changing Windows path...
wsl -d %WSL_DISTRO% -e bash -c "wslpath -u '%CURRENT_DIR%'" > temp_path.txt
set /p WSL_PATH=<temp_path.txt
del temp_path.txt
echo WSL path: %WSL_PATH%

REM 모듈 디렉토리 생성 및 모듈 폴더 복사
wsl -d %WSL_DISTRO% -e sudo mkdir -p /usr/lib/modules/%KERNEL_VERSION%
wsl -d %WSL_DISTRO% -e sudo cp -r "%WSL_PATH%%KERNEL_VERSION%" /usr/lib/modules/

REM WSL 재시작
echo Restarting WSL...
wsl --shutdown
timeout /t 5

REM 모듈 로드
echo Loading CAN modules...
wsl -d %WSL_DISTRO% -e sudo modprobe can
wsl -d %WSL_DISTRO% -e sudo modprobe vcan
wsl -d %WSL_DISTRO% -e sudo modprobe can_raw

REM Virtual CAN 인터페이스 생성
echo Creating vcan0 interface...
wsl -d %WSL_DISTRO% -e sudo ip link add dev vcan0 type vcan
wsl -d %WSL_DISTRO% -e sudo ip link set up vcan0

REM net-tools 설치 (ifconfig 사용을 위해)
echo Installing net-tools for ifconfig...
wsl -d %WSL_DISTRO% -e sudo apt-get install -y net-tools

REM 인터페이스 확인 (ifconfig 명령을 전체 경로로 지정)
echo Checking vcan0 interface...
wsl -d %WSL_DISTRO% -e bash -c "/sbin/ifconfig vcan0"

REM NOPASSWD 설정 복원 (보안을 위해)
echo Restoring sudo security...
wsl -d %WSL_DISTRO% -e sudo bash -c "sudo sed -i '/%%sudo ALL=(ALL) NOPASSWD: ALL/d' /etc/sudoers"

echo Setup completed.
echo Press any key to close this window...
pause >nul