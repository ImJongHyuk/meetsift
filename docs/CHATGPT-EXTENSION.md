# ChatGPT 확장

MeetSift 기본판은 MIT 라이선스이며 로컬 모델, 외부 서버와 OpenRouter를
사용합니다. ChatGPT 계정 연결은 기본판에 포함되지 않습니다.

선택 확장은 별도 저장소
[meetsift-chatgpt](https://github.com/ImJongHyuk/meetsift-chatgpt)에 있습니다.
확장에 포함된 OpenAI SDK와 공식 암호화 어댑터는 비상업 조건을 따릅니다.
회사·고용주·고객의 운영이나 상업적 이익을 위한 사용은 무료여도 비상업
범위에서 제외됩니다. 확장 라이선스를 먼저 확인하세요.

## 소스 설치

MeetSift 소스 폴더 밖에 확장 저장소를 복제하고 Node.js 22 이상에서 실행합니다.

```powershell
git clone https://github.com/ImJongHyuk/meetsift-chatgpt.git
Set-Location meetsift-chatgpt
npm ci
npm run build
$env:MEETSIFT_CHATGPT_EXTENSION = (Resolve-Path '.\dist\index.js').Path
```

같은 PowerShell에서 `MeetSift.exe` 또는 소스 앱을 실행하세요. 환경변수는
확장의 빌드된 `dist/index.js` **절대 경로**여야 합니다. 압축 배포된 확장도
폴더 전체를 보존해야 합니다. 확장을 바꾸면 앱을 다시 실행합니다.

앱 상단에 **ChatGPT 연결**이 나타나면 로그인하고 회의록 공급자를
**ChatGPT 확장**으로 선택합니다. 기존 앱의 저장소와 OS 암호화 형식은
유지되므로 같은 사용자 프로필의 기존 연결 정보를 재사용할 수 있습니다.
기본판은 확장이 없을 때도 해당 로그인 파일을 삭제하지 않습니다.

확장을 사용하지 않으려면 환경변수를 지우고 앱을 다시 시작합니다.

```powershell
Remove-Item Env:MEETSIFT_CHATGPT_EXTENSION -ErrorAction SilentlyContinue
```

## 신뢰와 배포 경계

확장은 Electron 메인 프로세스에서 실행되는 신뢰할 수 있는 로컬 코드입니다.
공식 출처와 라이선스를 확인한 확장만 설치하세요. 기본판은 확장을 자동으로
내려받거나 포함하지 않습니다. 확장은 OS 암호화 API와 해당 앱의 로그인
저장소를 사용하며, 인증 토큰을 렌더러로 반환하지 않습니다.

확장 API 버전은 1입니다. `createMeetSiftChatGPT(host)` 팩터리는 `apiVersion`,
`available`, `session`, `login`, `logout`, `cancelLogin`, `models`, `generate`,
`onSession`을 제공합니다. 기본판의 MIT 라이선스는 확장 SDK의 비상업 조건이나
OpenAI 서비스 이용 자격을 바꾸지 않습니다.
