# data/

| 파일 | 커밋 | 설명 |
|---|---|---|
| `sentences.csv` | ✅ | 연습 문장 30개 (id, text, level, category). id는 고정 UUID라 DB와 일치 |
| `eval_manifest_example.csv` | ✅ | 평가 manifest 작성 예시 |
| `eval/manifest.csv` | ✅ | 실제 평가 목록 (음성 경로·정답) |
| `eval/*.wav` | ❌ | 평가 녹음 원본 — 동의 받은 음성, 비공개 보관 |
| `raw/`, `private/` | ❌ | 기타 원본 |

자세한 내용은 `docs/데이터명세서.md`를 참고하세요.
