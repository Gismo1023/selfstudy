# 🎙️ AI 말하기 코치 (2팀)

한국어 문장을 듣고 따라 말하면 **STT 전사 결과를 정답과 비교**해 누락·대체·삽입된 어절을 표시하고, WER/CER와 재연습 안내를 음성(TTS)으로 들려주는 Streamlit 서비스입니다.

> ⚠️ 핵심 지표는 **전사 일치도**입니다. STT 전사가 정답과 같아도 실제 발음이 정확하다는 보장은 없으며, 이 서비스는 발음 진단·임상 평가 도구가 아닙니다.

## 주요 기능

| 기능 | 설명 |
|---|---|
| 문장 선택 | 난이도 3단계 × 10문장 (숫자·겹받침·잰말놀이·외래어 포함) |
| 정답 듣기 | edge-tts 한국어 음성 |
| 녹음·업로드 | 브라우저 마이크 또는 WAV 업로드 |
| 전사 | faster-whisper (CPU, int8) |
| 평가 | Levenshtein 정렬 직접 구현, WER(어절)·CER(문자, 공백 제외) |
| 피드백 | 오류 유형별 안내 문구 + TTS 음성 |
| 이력 | PostgreSQL 저장, 시도별 WER/CER 추이·재연습 비교 |
| 대시보드 | 오류 유형 빈도, 난이도별 평균, 전처리 전후·모델 비교 |

## 처리 흐름

```
녹음/WAV → 검사(형식·길이) → 전처리(모노·16kHz·무음 검사·앞뒤 무음 제거·음량 정규화)
→ STT → 정규화 → 정렬(S/D/I) → WER/CER → 피드백 문구 → TTS → DB 저장 → 결과·이력 화면
```

---

## 1. 설치

**필요 환경:** Python 3.10 이상, (권장) ffmpeg, 인터넷(TTS·최초 모델 다운로드)

```bash
git clone https://github.com/<팀>/<저장소>.git
cd <저장소>

python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 2. DB 설정 (Neon PostgreSQL)

1. [Neon](https://neon.tech)에서 프로젝트 생성 → **Connection string** 복사
2. 환경변수 파일 생성 후 `DATABASE_URL` 입력
   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   ```
3. 테이블 생성 + 문장 30개 적재
   ```bash
   python scripts/seed_sentences.py --init
   ```
   `✔ 적재 완료 (난이도별 문장 수): {1: 10, 2: 10, 3: 10}` 이 나오면 성공입니다.

> DB 없이도 앱은 실행됩니다. 문장은 `data/sentences.csv`에서 읽고, 결과 화면은 정상 표시되며 이력 저장만 실패 경고가 뜹니다.

## 3. 실행

```bash
streamlit run app.py
```
브라우저에서 `http://localhost:8501` 접속. **첫 분석은 STT 모델 다운로드 때문에 1~2분** 걸릴 수 있습니다.

(선택) 네트워크 장애 대비 TTS 음성 미리 만들기:
```bash
python scripts/make_tts_fallback.py --per-level 2
```

## 4. 테스트

```bash
pytest tests/ -v
```

| 파일 | 내용 |
|---|---|
| `tests/test_core.py` | 수작업 검증 10건(WER/CER·S/D/I), 오류 위치, N=0, 100% 초과, 피드백 조사 처리, jiwer 교차 검증 |
| `tests/test_audio.py` | T06 무음·깨진 WAV, 비WAV, 길이 제한, 모노·16kHz 변환 |
| `tests/test_resilience.py` | T08 TTS 실패·폴백, T09 DB 장애(CSV 폴백·저장 실패·조회 오류) |

## 5. 평가 실험 (전처리 전후 · 모델 비교)

1. 평가 녹음 30건 이상을 `data/eval/`에 저장 (Git에 올라가지 않음, 녹음 동의서 필수)
2. `data/eval_manifest_example.csv`를 참고해 `data/eval/manifest.csv` 작성
3. 실행
   ```bash
   python scripts/run_eval.py --models base small --compare-preprocess
   ```
4. 결과: `reports/eval_results.csv`(건별), `reports/eval_summary.csv`(조건별 평균) → 대시보드 화면에 자동 표시

## 6. 평가 기준 (정규화·토큰화 정책)

| 항목 | 정책 |
|---|---|
| 공백 | 양끝 제거, 연속 공백 → 1칸 |
| 문장부호 | `. , ? ! ~ … " '` 등 제거 |
| 숫자 | 변환하지 않음 ("3개" vs "세 개"는 오류로 집계) |
| WER | 공백 기준 **어절** 단위 |
| CER | **공백 제외** 문자 단위 |
| 공식 | `(S + D + I) / N`, N=정답 토큰 수. N=0이면 계산하지 않음(N/A), 100% 초과 허용 |

## 7. 저장소 구조

```text
├── app.py                  UI-01 연습 홈
├── pages/                  UI-02 결과 · UI-03 이력 · UI-04 대시보드
├── src/                    audio · stt · tts · core · db · ui_common
├── sql/schema.sql          DB 스키마
├── data/                   sentences.csv, 평가 manifest 예시 (음성 원본 제외)
├── scripts/                seed_sentences · run_eval · make_tts_fallback
├── tests/                  단위·장애 테스트
├── reports/                평가 보고서·결과
├── docs/                   요구사항·설계·ERD·데이터 명세·동의서·테스트·시연·회고
└── assets/tts_fallback/    시연용 사전 생성 TTS
```

## 8. 개인정보·보안

- 음성 원본은 **저장하지 않습니다**(메모리에서 처리 후 폐기). DB에는 전사문·지표만 저장합니다.
- 로그인이 없어 익명 세션 ID로 이력을 구분합니다. **개인별 비공개 이력은 보장하지 않습니다.**
- API 키·DB 주소는 `.env` 또는 Streamlit Cloud Secrets에만 보관합니다.
- 평가 녹음은 `docs/녹음동의서.md` 동의를 받은 뒤 비공개 저장소에만 보관하고, 프로젝트 종료 후 30일 이내 삭제합니다.

## 9. 배포 (Streamlit Community Cloud)

1. GitHub `main` 브랜치 연결 → Main file: `app.py`
2. **Settings → Secrets**에 입력
   ```toml
   DATABASE_URL = "postgresql://...?sslmode=require"
   STT_MODEL = "base"
   ```
3. 메모리 부족 시 `STT_MODEL = "tiny"`로 낮추고, 배포 실패 시 로컬 실행으로 시연합니다(`docs/시연시나리오.md`).

## 10. 자주 나는 오류

| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError: src` | 프로젝트 루트에서 `streamlit run app.py` 실행 |
| `st.audio_input` 없음 | `pip install -U "streamlit>=1.39"` |
| 첫 분석이 매우 느림 | 모델 다운로드 중(정상). 이후 캐시 사용 |
| 정답 듣기 실패 | 인터넷 확인 또는 `make_tts_fallback.py`로 사전 생성 |
| 이력이 안 보임 | `.env`의 `DATABASE_URL` 확인 후 `seed_sentences.py --init` 실행 |

## 팀

| 역할 | 이름 | 담당 파일 |
|---|---|---|
| PM·통합 | [ ] | README, docs/, 통합 |
| 데이터·음성 | [ ] | src/audio.py, data/, docs/데이터명세서.md |
| AI·평가 | [ ] | src/core.py, scripts/run_eval.py, tests/test_core.py, reports/ |
| 서비스·DB | [ ] | src/stt.py, src/tts.py, src/db.py, sql/ |
| UI·배포 | [ ] | app.py, pages/, src/ui_common.py, 배포 |
