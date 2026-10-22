"""UI-01 연습 홈 — 문장 선택 → 정답 듣기 → 녹음/업로드 → 분석."""
import time

import streamlit as st

from src import audio, core, db, stt  # noqa: E402
from src.audio import AudioError  # noqa: E402
from src.stt import STTError  # noqa: E402
from src.ui_common import (  # noqa: E402
    LEVEL_NAMES,
    LEVELS,
    init_session,
    render_sidebar,
    speak,
)

session_id = init_session()
render_sidebar()


# ---------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=600)
def load_sentences(level):
    """db.list_sentences 내부에서 DB 실패 시 CSV 폴백 처리."""
    return db.list_sentences(level)


# ---------------------------------------------------------------
# 파이프라인: 검사·전처리 → STT → 평가 → 피드백 TTS → DB 저장
# ---------------------------------------------------------------
def run_pipeline(file, sentence: dict) -> dict:
    timings = {}
    t_start = time.perf_counter()

    # 1) 오디오 검사·전처리 (AudioError 발생 가능)
    t = time.perf_counter()
    y, sr = audio.load_and_validate(file)
    y, sr = audio.preprocess(y, sr)
    timings["audio_ms"] = int((time.perf_counter() - t) * 1000)

    # 2) STT (STTError 발생 가능)
    stt_out = stt.transcribe(y, sr)
    hypothesis = stt_out.get("text", "") or ""
    timings["stt_ms"] = stt_out.get("stt_ms", 0)

    # 3) 정규화·정렬·지표·피드백
    t = time.perf_counter()
    ref_n = core.normalize(sentence["text"])
    hyp_n = core.normalize(hypothesis)
    status = "ok" if hyp_n else "empty_transcript"
    metrics = core.compute_metrics(ref_n, hyp_n)
    errors = core.align(ref_n, hyp_n, unit="word")
    feedback = core.make_feedback(errors, n_ref=metrics["N"])
    timings["core_ms"] = int((time.perf_counter() - t) * 1000)

    # 4) 피드백 TTS (실패해도 텍스트 피드백 유지)
    t = time.perf_counter()
    feedback_audio = speak(feedback)
    timings["tts_ms"] = int((time.perf_counter() - t) * 1000)
    if feedback_audio is None and status == "ok":
        status = "tts_failed"

    timings["total_ms"] = int((time.perf_counter() - t_start) * 1000)

    # 5) DB 저장 (실패 시 None → 결과 화면에서 경고만 표시)
    run_id = db.save_run(
        session_id=session_id,
        sentence_id=sentence["id"],
        transcript=hypothesis,
        metrics=metrics,
        latency_ms=timings["total_ms"],
        status=status,
        errors=errors,
    )

    return {
        "sentence": sentence,
        "reference": ref_n,
        "transcript": hypothesis,
        "hypothesis": hyp_n,
        "metrics": metrics,
        "errors": errors,
        "feedback": feedback,
        "feedback_audio": feedback_audio,
        "timings": timings,
        "status": status,
        "run_id": run_id,
    }


# ---------------------------------------------------------------
# 화면
# ---------------------------------------------------------------
st.title("🎙️ AI 말하기 코치")
st.caption("문장을 듣고 따라 말해 보세요. STT 전사 결과를 정답과 비교해 드립니다.")

col_left, col_right = st.columns([1, 1], gap="large")

# ── 왼쪽: 문장 선택 + 정답 듣기 ──────────────────────────
with col_left:
    st.subheader("① 문장 선택")
    level_label = st.radio("난이도", list(LEVELS.keys()), horizontal=True)
    df = load_sentences(LEVELS[level_label])

    if df is None or df.empty:
        st.error("연습 문장을 불러오지 못했습니다. DB 연결 또는 data/sentences.csv를 확인해 주세요.")
        st.stop()

    sentences = df.to_dict("records")
    ids = [s["id"] for s in sentences]

    # '다시 연습'으로 돌아온 경우 같은 문장 기본 선택
    retry_id = st.session_state.pop("retry_sentence_id", None)
    default_idx = ids.index(retry_id) if retry_id in ids else 0

    sentence = st.selectbox(
        "연습할 문장",
        sentences,
        index=default_idx,
        format_func=lambda s: f"[{LEVEL_NAMES.get(s['level'], '-')}] {s['text']}",
    )

    st.markdown(f"#### “{sentence['text']}”")

    if st.button("🔊 정답 듣기", use_container_width=True):
        with st.spinner("음성 생성 중..."):
            answer_audio = speak(sentence["text"])
        if answer_audio:
            st.audio(answer_audio, format="audio/mp3", autoplay=True)
        else:
            st.warning("음성 생성에 실패했습니다. 네트워크를 확인한 뒤 다시 눌러 주세요.")

# ── 오른쪽: 녹음/업로드 + 분석 ───────────────────────────
with col_right:
    st.subheader("② 따라 말하기")
    tab_rec, tab_up = st.tabs(["🎙️ 마이크 녹음", "📁 WAV 업로드"])
    with tab_rec:
        recorded = st.audio_input("녹음 버튼을 누르고 문장을 읽어 주세요")
    with tab_up:
        uploaded = st.file_uploader("WAV 파일 업로드", type=["wav"])

    audio_file = recorded or uploaded

    if st.button(
        "🚀 분석하기",
        type="primary",
        use_container_width=True,
        disabled=audio_file is None,
    ):
        try:
            with st.spinner("전사 및 분석 중... (첫 실행은 모델 로딩으로 오래 걸릴 수 있습니다)"):
                result = run_pipeline(audio_file, sentence)
        except AudioError as e:
            st.warning(f"⚠️ {e} — 다시 녹음해 주세요.")
        except STTError:
            st.error("음성 인식 모델을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        except Exception:
            st.error("처리 중 예기치 않은 오류가 발생했습니다. 다시 시도해 주세요.")
        else:
            st.session_state.last_result = result
            st.switch_page("pages/result.py")

    if audio_file is None:
        st.caption("녹음하거나 WAV 파일을 올리면 분석 버튼이 활성화됩니다.")
