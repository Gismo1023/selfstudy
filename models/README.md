# models/

모델 파일은 용량·라이선스 문제로 **Git에 올리지 않습니다**(`.gitignore` 처리).

- **STT:** faster-whisper 모델은 첫 실행 시 Hugging Face 캐시(`~/.cache/huggingface`)에 자동 다운로드됩니다.
  - 모델 선택: `.env`의 `STT_MODEL` (`tiny` / `base` / `small`)
  - 시연 전날 한 번 실행해 미리 받아 두세요.
- **TTS:** edge-tts는 온라인 서비스라 로컬 모델이 없습니다.
- 팀 자체 모델을 추가할 경우 이 폴더에 두고 다운로드 경로·라이선스를 여기에 기록합니다.
