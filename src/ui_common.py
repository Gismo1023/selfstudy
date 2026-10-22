"""UI 공통 헬퍼 — 세션 ID, TTS 캐싱, 사이드바, 포맷 함수.

모든 페이지(app.py, pages/*)에서 import 해서 사용합니다.
"""
import uuid

import streamlit as st

from src import tts

LEVELS = {"전체": None, "쉬움": 1, "보통": 2, "어려움": 3}
LEVEL_NAMES = {1: "쉬움", 2: "보통", 3: "어려움"}
TTS_VOICE = "ko-KR-SunHiNeural"


def init_session() -> str:
    """익명 세션 ID 생성(최초 1회). 로그인 없음 → 비공개 이력 보장 X."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id


@st.cache_data(show_spinner=False, max_entries=200)
def _tts_cached(text: str) -> bytes:
    audio_bytes = tts.synthesize(text, TTS_VOICE)
    if audio_bytes is None:
        # 예외를 던지면 st.cache_data가 실패 결과를 캐싱하지 않음 → 재시도 가능
        raise RuntimeError("TTS 생성 실패")
    return audio_bytes


def speak(text: str) -> bytes | None:
    """TTS 음성(MP3 bytes) 반환. 실패 시 None (화면은 텍스트로 대체)."""
    try:
        return _tts_cached(text)
    except Exception:
        return None


def pct(value) -> str:
    """0.25 → '25.0%'. None(N=0) → 'N/A'. 100% 초과도 자르지 않음."""
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def get_attr(item, name):
    """ErrorItem(dataclass)과 dict(DB 조회 결과) 모두 지원."""
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def render_sidebar() -> None:
    sid = init_session()
    with st.sidebar:
        st.markdown("### 🎙️ AI 말하기 코치")
        st.caption(f"세션 ID: `{sid[:8]}`")
        st.divider()
        st.caption(
            "ℹ️ 결과는 **STT 전사 일치도(WER/CER)** 이며 실제 발음 정확도나 "
            "임상적 평가를 의미하지 않습니다."
        )
        st.caption(
            "🔒 음성 원본은 저장하지 않습니다. 로그인이 없으므로 이력은 "
            "현재 세션 기준으로만 조회되며 개인 비공개를 보장하지 않습니다."
        )
