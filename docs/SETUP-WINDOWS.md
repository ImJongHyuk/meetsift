# Windows x64 ZIP + WSL2 설치

Windows에서 데스크톱 앱을 실행하고, WSL2 Ubuntu에서 백엔드를 실행합니다. ZIP은 앱 폴더 배포이며 단일 실행 파일 설치판이 아닙니다. 외부 공급자를 사용하면 로컬 NVIDIA GPU는 필요하지 않습니다.

## 로컬 GPU 없이 시작하기

외부 서버나 OpenRouter를 사용할 경우 WSL2 Ubuntu와 아래의 Python·uv·FFmpeg만 준비하고 NVIDIA 드라이버·CUDA·모델 다운로드 단계는 건너뜁니다. 소스를 받은 후에는 `bash scripts/setup-backend.sh`로 **`--gpu` 없이** 설치하세요. 이후 아래의 연결 토큰 생성과 백엔드 실행 명령을 사용합니다.

앱 상단의 **모델·공급자 설정**에서 전사와 화자 분리를 각각 외부 서버 또는 OpenRouter로 바꾸고 주소·모델·API 키를 저장합니다. 회의록도 별도로 설정할 수 있습니다. [공급자 안내](PROVIDERS.md)에서 API 계약과 지원 프리셋을 확인하세요. FFmpeg 변환과 작업 저장을 담당하는 비GPU 백엔드는 계속 필요합니다.

## 1. WSL2와 GPU 준비

Windows에 NVIDIA 드라이버를 설치한 뒤 관리자 PowerShell에서 실행합니다.

```powershell
wsl --install -d Ubuntu
```

필요한 재부팅과 Ubuntu 사용자 생성을 마친 뒤, Ubuntu 터미널에서 확인합니다.

```bash
nvidia-smi
```

GPU가 보이지 않으면 Windows 드라이버와 WSL2 설정부터 확인하세요. 추론 환경은 CUDA 12.6용 패키지를 사용합니다. WSL 안에 별도의 Linux 디스플레이 드라이버를 설치하지 않습니다.

Ubuntu에서 기본 도구를 준비합니다.

```bash
sudo apt update
sudo apt install -y git ffmpeg libsndfile1 pipx
pipx install uv
pipx ensurepath
```

Ubuntu 터미널을 새로 연 뒤 실행합니다.

```bash
uv python install 3.12
```

## 2. 소스·모델 설치와 백엔드 실행

Ubuntu 홈 아래에 소스를 받습니다. 아래 경로는 이후 Windows의 토큰 전달 명령과 맞춰져 있습니다. 다른 위치를 사용하면 해당 명령의 경로도 함께 변경하세요.

```bash
cd ~
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
bash scripts/setup-backend.sh --gpu
backend/.venv-native/bin/python scripts/download-models.py
```

기본 설치는 MOSS와 Nemotron입니다. Python 환경은 `backend/.venv*`, 모델은 `models/`에 저장합니다. 실제 다운로드 용량과 디스크 여유를 확인하세요.

**Whisper INT8도 사용하려는 경우에만** 다음을 추가로 실행합니다. 설정 스크립트는 추론 환경을 다시 만들고 의존성을 설치합니다.

```bash
MEETING_INSTALL_WHISPER=1 bash scripts/setup-backend.sh --gpu
backend/.venv-native/bin/python scripts/download-models.py --whisper
```

앱과 백엔드가 공유할 임의 토큰을 생성하고 서버를 실행합니다. 토큰 파일은 이 컴퓨터의 `.local-data/`에만 두며, 화면에 출력하거나 저장소에 올리지 않습니다. 기존 파일이 있으면 재사용합니다.

```bash
mkdir -p .local-data
umask 077
test -s .local-data/api-token || backend/.venv/bin/python -c 'from pathlib import Path; import secrets; Path(".local-data/api-token").write_text(secrets.token_urlsafe(32))'
export MEETING_API_TOKEN="$(cat .local-data/api-token)"
export MEETING_DATA_DIR="$PWD/.local-data"
bash scripts/run-backend.sh
```

이 Ubuntu 터미널을 열어 둡니다. 서버는 `127.0.0.1:8765`를 사용합니다. 다음에 실행할 때는 저장소 폴더로 이동해 마지막 세 명령(`export` 두 줄과 `run-backend.sh`)을 다시 실행하면 됩니다. 모델을 다시 내려받을 필요는 없습니다.

## 3. Windows에서 앱 실행

[Releases](https://github.com/ImJongHyuk/meetsift/releases)의 `meetsift-<version>-win-x64.zip`을 내려받아, 예를 들어 `C:\Apps\meetsift`에 **모두 압축 해제**합니다.

일반 PowerShell을 열어 실행합니다. 토큰을 명령에 직접 적지 않고 WSL 파일에서 환경변수로 읽습니다. WSL 배포판 이름이나 소스 경로를 바꿨다면 이 명령도 맞춰 변경하세요.

```powershell
$env:MEETING_EXTERNAL_BACKEND = '1'
$env:MEETING_API_TOKEN = (wsl -d Ubuntu -- bash -lc 'cat "$HOME/meetsift/.local-data/api-token"').Trim()
Invoke-RestMethod http://127.0.0.1:8765/health
Set-Location 'C:\Apps\meetsift'
Start-Process -FilePath '.\MeetSift.exe'
```

상태 확인에서 `ok: true`가 나와야 합니다. 앱이 정상 실행되면 **파일 가져오기 → 전사 시작 → 원음 대조·수정 → 내보내기** 순서로 사용합니다. ChatGPT 회의록 생성은 별도 비상업 확장을 설치하고 로그인한 경우에 사용할 수 있습니다. [확장 안내](CHATGPT-EXTENSION.md)를 참고하세요.

앱을 다시 실행할 때도 같은 PowerShell 환경변수 설정이 필요합니다. ZIP의 실행 파일만 더블클릭하면 WSL 백엔드 연결 설정이 전달되지 않습니다. 앱을 닫아도 외부 WSL 서버는 계속 실행되며, Ubuntu 서버 터미널에서 `Ctrl+C`로 종료할 수 있습니다.

## 소스에서 앱 실행하기

Windows에 Node.js 22 이상과 Git을 설치하고 소스를 받습니다.

```powershell
git clone https://github.com/ImJongHyuk/meetsift.git
Set-Location meetsift
npm ci
$env:MEETING_EXTERNAL_BACKEND = '1'
$env:MEETING_API_TOKEN = (wsl -d Ubuntu -- bash -lc 'cat "$HOME/meetsift/.local-data/api-token"').Trim()
npm start
```

Windows 소스 폴더와 WSL 소스 폴더는 별개입니다. 모델과 데이터는 WSL 쪽에 두고, 같은 릴리스 버전의 앱과 백엔드를 사용하세요.

## 연결되지 않을 때

- `/health`에 연결되지 않으면 WSL 서버가 켜져 있는지, Windows에서 WSL의 localhost에 접근 가능한지 확인합니다. 필요하면 `wsl --update` 후 WSL을 재시작합니다.
- 상태 확인은 되지만 작업 목록이나 업로드가 실패하면 두 프로세스의 `MEETING_API_TOKEN` 값이 같은지 확인하고 앱을 다시 시작합니다. 토큰은 로그나 이슈에 붙이지 않습니다.
- 모델·Python 경로 오류는 [백엔드 설정](../backend/README.md)의 환경변수를 확인합니다. 기본 모델 설치 없이 UI만 실행하면 전사를 완료할 수 없습니다.
- GPU 메모리가 부족하면 더 작은 모델이나 외부 공급자를 선택하세요. 화자·겹침·청크 경계의 검토 표시는 원음과 대조해야 합니다. 메모리 사용량은 모델과 녹음 길이에 따라 달라집니다.

원음·전사문·작업 결과는 기본 안내대로 실행했다면 WSL 소스 폴더의 `.local-data/`에 남습니다. 앱의 ChatGPT 로그인 정보는 Windows 사용자별 앱 데이터에 OS 암호화로 저장합니다. 배포 ZIP에 모델·녹음·로그인 정보는 포함하지 않습니다.
