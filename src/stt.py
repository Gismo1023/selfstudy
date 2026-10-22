"""STT — faster-whisper 기반 한국어 전사.

모델 이름은 환경변수 STT_MODEL (기본 'base'). 배포는 base+int8, 로컬 평가는 small 권장.
모델은 프로세스당 1회만 로드(lru_cache)하므로 Streamlit 재실행 시에도 재사용됩니다.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

import numpy as np

DEFAULT_MODEL = os.getenv("STT_MODEL", "base")
COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "int8")


class STTError(Exception):
    """모델 로드 또는 추론 실패."""


@lru_cache(maxsize=3)
def get_model(name: str = DEFAULT_MODEL):
    try:
        from faster_whisper import WhisperModel
        return WhisperModel(name, device="cpu", compute_type=COMPUTE_TYPE)
    except Exception as exc:  # 다운로드 실패, 메모리 부족 등
        raise STTError(f"STT 모델({name})을 불러오지 못했습니다: {exc}") from exc


def transcribe(y: np.ndarray, sr: int = 16000, model_name: str | None = None) -> dict:
    """16kHz 모노 파형 → {"text": str, "stt_ms": int}. 빈 전사도 정상 반환."""
    if sr != 16000:
        raise STTError("STT 입력은 16kHz여야 합니다(audio.preprocess 먼저 호출)")
    model = get_model(model_name or DEFAULT_MODEL)
    t = time.perf_counter()
    try:
        segments, _info = model.transcribe(
            np.asarray(y, dtype=np.float32),
            language="ko",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as exc:
        raise STTError(f"음성 인식 중 오류: {exc}") from exc
    return {"text": text, "stt_ms": int((time.perf_counter() - t) * 1000)}
