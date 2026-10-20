# Windows 설치

설치·검증·문제 해결의 전체 절차는 [Install and verify](INSTALL.md)에 있습니다.

Windows 11, WSL2 Ubuntu, Git, Node.js 22.12 이상을 준비한 후 실행합니다.
로컬 GPU 모드는 WSL에서 보이는 NVIDIA GPU와 호환 Windows 드라이버가 필요합니다.

```powershell
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
.\scripts\start-windows.ps1
```

GPU 없이 외부 서버·OpenRouter를 사용할 때는 `-Mode Remote`로 설치한 뒤,
앱에서 전사와 화자 분리 공급자를 모두 설정하세요. 회의록 공급자는 별도로 선택합니다.

설치 스크립트는 드라이버를 설치하지 않습니다. GPU 모드는 CUDA 연산과 두 기본
모델의 실제 실행까지 성공해야 설치 완료를 표시합니다. API 연결만 성공한 것을
GPU 추론 검증으로 간주하지 않습니다.

ChatGPT는 함께 포함되며 별도 확장 저장소를 설치할 필요가 없습니다.
MeetSift 자체 코드는 MIT이지만 포함된 SDK와 공식 암호화 어댑터에는 비상업
조건이 적용됩니다. [라이선스 범위](../LICENSES.md)와 [ChatGPT 안내](CHATGPT-EXTENSION.md)를 확인하세요.
