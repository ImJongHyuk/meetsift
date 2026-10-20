# MeetSift

**Turn conversations into clear meeting notes.**

한국어 음성을 전사하고 화자를 나누어 회의록으로 정리하는 MIT 데스크톱 앱입니다. 녹음 파일을 로컬 GPU 또는 설정한 서버·OpenRouter에서 처리하고, 원음을 들으며 문장과 화자 이름을 수정할 수 있습니다. 작성 규칙을 `.md`·`.txt`로 불러와 선택한 모델 공급자로 회의록을 만들고 Markdown·JSON으로 내보냅니다.

## Windows에서 시작

1. [Releases](https://github.com/ImJongHyuk/meetsift/releases)에서 **Windows x64 ZIP**을 내려받아 폴더 전체를 압축 해제합니다.
2. [Windows·WSL2 설치 안내](docs/SETUP-WINDOWS.md)에 따라 백엔드를 준비합니다. 로컬 GPU를 사용할 때만 CUDA 환경과 모델을 추가 설치합니다.
3. 같은 안내의 PowerShell 명령으로 백엔드 연결 환경변수를 설정한 뒤, 압축을 푼 폴더의 **`MeetSift.exe`**를 실행합니다.

ZIP에는 데스크톱 앱이 들어 있습니다. **WSL2, Python, FFmpeg는 별도 설치**가 필요하며 로컬 GPU를 선택하면 **CUDA 추론 환경과 모델도 필요**합니다. 실행 파일만 다른 폴더로 옮기지 마세요. 첫 모델 설치에는 인터넷과 다운로드 공간이 필요합니다. 기본 공급자에서는 음성을 로컬에서 처리하고, 외부 공급자를 선택하면 해당 서버에 전달합니다.

기본 모델은 **MOSS 0.9B**, 대체 모델은 **Whisper INT8**입니다. Whisper를 쓰려면 설치 안내의 선택 단계를 추가로 진행하세요.

상단 **모델·공급자 설정**에서 전사·화자 분리·회의록을 각각 로컬 GPU, 외부 서버, OpenRouter로 설정할 수 있습니다. 회의록의 기본값은 로컬 모델 서버이며 사용할 모델을 선택해야 합니다. 서버 주소·모델·API 키, 화자 API 응답 계약과 데이터 전송 범위는 [공급자 설정 안내](docs/PROVIDERS.md)를 참고하세요.

## 가져올 수 있는 파일

- 음성: WAV, MP3, M4A, AAC, FLAC, OGG/OGA, OPUS, WMA, AIF/AIFF, AMR
- 동영상·컨테이너: MP4, M4V, MOV, MKV, WEBM, AVI, 3GP/3G2, MPEG/MPG, TS

FFmpeg가 파일의 첫 번째 음성 트랙을 읽어 전사용 WAV로 변환합니다. 동영상에는 음성 트랙이 있어야 하며, 실제 처리 가능 여부는 파일 내부 코덱과 설치된 FFmpeg에 따라 달라집니다. 앱에서 원음을 재생할 수 있는 코덱은 Electron/Chromium의 지원 범위에 따릅니다.

## 선택 사항: ChatGPT 확장

ChatGPT 계정 연결은 기본판에 포함되지 않으며 [별도 확장](https://github.com/ImJongHyuk/meetsift-chatgpt)으로 설치합니다. 확장을 설정하면 앱에 **ChatGPT 연결**이 나타나고 공식 OpenAI 인증 화면이 브라우저에서 열립니다. 별도 Platform API 키를 입력하지 않으며, 로그인한 계정에서 허용하는 모델과 공유 한도를 사용합니다.

**ChatGPT로 회의록 작성**을 누를 때 작성 규칙, 수정한 전사문, 화자 정보, 문장 ID, 시간과 검토 표시가 ChatGPT에 전송됩니다. 원음은 전송하지 않습니다. 인증 정보는 Electron 메인 프로세스에서 OS `safeStorage`로 암호화합니다.

확장에 포함된 공식 SDK와 암호화 어댑터에는 **비상업 조건**이 적용됩니다. MeetSift의 MIT 라이선스가 이 조건을 바꾸지 않습니다. 설치와 기존 로그인 유지 방법은 [ChatGPT 확장 안내](docs/CHATGPT-EXTENSION.md)를 참고하세요.

## 소스로 실행

Git과 Node.js 22 이상이 필요합니다. 백엔드는 [설치 안내](docs/SETUP-WINDOWS.md)에 따라 먼저 실행합니다.

```sh
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
npm ci
```

Windows PowerShell에서 `MEETING_EXTERNAL_BACKEND=1`과 WSL 백엔드의 동일한 `MEETING_API_TOKEN`을 설정한 뒤 실행합니다. 토큰 전달 명령은 [설치 안내](docs/SETUP-WINDOWS.md#3-windows에서-앱-실행)에 있습니다.

```powershell
npm start
```

`npm run build`는 타입 검사와 프로덕션 빌드를 수행합니다. `npm run dev`는 브라우저 UI 개발용이며, ChatGPT 연결은 Electron에서만 사용할 수 있습니다. 백엔드 설정과 API 계약은 [backend/README.md](backend/README.md)를 참고하세요.

## 처리 결과와 데이터

전사문과 회의록에는 인식·생성 오류가 있을 수 있습니다. 화자 연결과 겹침·청크 경계의 검토 표시를 원음과 대조하세요. 로컬 추론의 메모리 사용량은 모델·녹음 길이·실행 환경에 따라 달라집니다.

원음·작업 결과는 WSL의 설정한 데이터 폴더에 저장합니다. 배포 소스에 `.env`나 인증 토큰을 넣지 않으며, 설치 안내는 사용자의 컴퓨터에서 새 연결 토큰을 생성합니다.

## 배포와 라이선스

MeetSift 자체 코드는 [MIT](LICENSE)이며 상업적 이용과 수정·재배포를 허용합니다. 저작권·허가 고지는 유지해야 합니다. 의존성·모델·외부 서비스에는 각각의 조건이 적용되고, 별도 ChatGPT 확장에는 비상업 조건이 있습니다. 자세한 범위는 [라이선스 안내](LICENSES.md)를 참고하세요.

저장소 공개 여부와 npm 배포 방지는 별개이며, `package.json`의 `private: true`는 실수로 npm에 게시하는 것을 막기 위한 설정입니다.
