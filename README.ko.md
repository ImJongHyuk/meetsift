<p align="center">
  <img src="docs/assets/meetsift-icon.png" width="112" height="112" alt="MeetSift">
</p>

# MeetSift

[English](README.md) · 한국어

**녹음에서 회의록까지.**

녹음을 가져와 전사문과 화자를 확인하고, 결정사항과 할 일이 담긴 회의록을 만드세요.

- 갤럭시 음성 녹음의 **M4A**, 일반 오디오 파일과 음성이 있는 동영상을 가져옵니다.
- 타임스탬프와 함께 듣고, 전사문과 화자 이름을 수정하고, Markdown·JSON으로 내보냅니다.
- 전사·화자 분리·회의록 공급자를 각각 설정합니다. 단계에 따라 로컬 NVIDIA GPU, 외부 서버, OpenRouter, ChatGPT를 사용할 수 있습니다.

화면과 기본 프롬프트는 한국어입니다. 인식 언어는 선택한 모델에 따라 달라집니다.

## Windows에서 시작하기

**Windows 11, WSL2 Ubuntu, Git, Node.js 22.12+**가 필요합니다. 로컬 추론에는 호환되는 NVIDIA Windows 드라이버도 필요합니다.

```powershell
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
.\scripts\start-windows.ps1
```

설치 스크립트는 독립된 Python 환경과 고정된 버전의 MOSS·Nemotron 모델을 설치하고, 앱을 빌드하고 CUDA를 점검합니다. 다운로드 용량은 수 GB이며 Ubuntu의 sudo 비밀번호 입력이 필요할 수 있습니다. GPU 설치는 전사와 화자 분리를 위한 것입니다. 회의록을 만들려면 ChatGPT나 모델 서버를 연결하세요.

외부 오디오 공급자를 쓰려면 `-Mode Remote`로 설치하고 **모델·공급자 설정**에서 전사와 화자 분리를 모두 설정하세요. [Windows ZIP](https://github.com/ImJongHyuk/meetsift/releases/latest)도 제공합니다.

[설치·문제 해결](docs/INSTALL.md) · [공급자 설정](docs/PROVIDERS.md) · [ChatGPT](docs/CHATGPT-EXTENSION.md)

## AI Agent로 설치·검증

다른 기기의 터미널 AI Agent에 아래 요청을 붙여 넣으세요. **녹음 경로와 화자 수만 바꾸면 됩니다.**

```text
https://github.com/ImJongHyuk/meetsift 를 클론하고 AGENTS.md에 따라 설치해줘.
D:\Recordings\sample.m4a(화자 2명)로 로컬 GPU 통합 테스트를 실행하고 결과를 로컬에 남겨줘.
GPU를 쓸 수 없거나 테스트가 실패하면 원인과 다음 조치를 알려줘.
```

NVIDIA GPU와 처리 권한이 있는 짧은 녹음이 필요합니다. [직접 실행·Ubuntu 명령](docs/GPU-TEST.md)

## 데이터와 라이선스

로컬 오디오 공급자를 쓰면 녹음과 처리 결과는 해당 기기에 보관됩니다. 외부 오디오 공급자에는 음성이, 회의록 공급자에는 텍스트가 전달됩니다. ChatGPT에는 작성 규칙과 검토한 전사문, 화자 표시, 타임스탬프가 전달됩니다. 데스크톱 인증 정보는 운영체제의 암호화 기능으로 보호합니다. 생성된 전사문과 화자 표시는 사용 전에 확인하세요.

MeetSift 자체 코드의 라이선스는 **MIT**입니다. 포함된 OpenAI ChatGPT SDK와 인증 어댑터에는 원래의 **비상업 라이선스**가 적용되며, 전체 앱이 MIT인 것은 아닙니다. SDK 약관은 비용을 받지 않더라도 회사·고용주·고객의 업무 목적 사용을 제외합니다. [적용 범위](LICENSES.md)와 [원문 약관](extensions/chatgpt/vendor/siwc-local/LICENSE)을 확인하세요.

## 개발

```sh
npm ci
npm run check
```

`npm run desktop`은 빌드된 앱을, `npm run dev`는 브라우저 UI만 실행합니다.

[Agent 안내](AGENTS.md) · [백엔드 API](backend/README.md) · [기여 안내](CONTRIBUTING.md)
