"""오디오 입력·검사·전처리.

load_and_validate(file) → (y, sr)   : 형식·길이 검사
preprocess(y, sr, enhance=True) → (y, 16000) : 모노·16kHz·무음 검사 (+ 앞뒤 무음 제거·음량 정규화)

enhance=False 는 '전처리 전(기준선)' 조건으로, 평가 스크립트의 전처리 전후 비교에 사용합니다.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np

TARGET_SR = 16000
MIN_SEC = 0.5
MAX_SEC = 30.0
SILENCE_RMS = 1e-3     # 이보다 작으면 무음으로 판단
TRIM_TOP_DB = 30       # 앞뒤 무음 제거 기준
MIN_VOICED_SEC = 0.3


class AudioError(Exception):
    """사용자에게 그대로 보여줄 수 있는 오디오 오류."""


# ---------------------------------------------------------------
def _read_bytes(file) -> bytes:
    if file is None:
        raise AudioError("음성 파일이 없습니다")
    if isinstance(file, (bytes, bytearray)):
        return bytes(file)
    if isinstance(file, (str, Path)):
        return Path(file).read_bytes()
    if hasattr(file, "getvalue"):          # Streamlit UploadedFile (audio_input / file_uploader)
        return file.getvalue()
    if hasattr(file, "read"):
        return file.read()
    raise AudioError("지원하지 않는 입력입니다")


def _decode_wav(data: bytes) -> tuple[np.ndarray, int]:
    """soundfile 우선, 없으면 scipy로 디코딩. float32, shape (frames,) 또는 (frames, ch)."""
    try:
        import soundfile as sf
        y, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        return y, int(sr)
    except ImportError:
        from scipy.io import wavfile
        sr, y = wavfile.read(io.BytesIO(data))
        if np.issubdtype(y.dtype, np.integer):
            y = y.astype(np.float32) / np.iinfo(y.dtype).max
        return y.astype(np.float32), int(sr)


def load_and_validate(file) -> tuple[np.ndarray, int]:
    data = _read_bytes(file)
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AudioError("WAV 형식이 아니거나 손상된 파일입니다")
    try:
        y, sr = _decode_wav(data)
    except AudioError:
        raise
    except Exception as exc:
        raise AudioError("WAV 파일을 읽을 수 없습니다(손상된 파일)") from exc

    if y.size == 0 or sr <= 0:
        raise AudioError("비어 있는 음성 파일입니다")
    duration = y.shape[0] / sr
    if duration < MIN_SEC:
        raise AudioError(f"녹음이 너무 짧습니다({duration:.1f}초)")
    if duration > MAX_SEC:
        raise AudioError(f"녹음이 너무 깁니다({duration:.0f}초, 최대 {MAX_SEC:.0f}초)")
    return y, sr


# ---------------------------------------------------------------
def _resample(y: np.ndarray, sr: int, target: int) -> np.ndarray:
    if sr == target:
        return y
    try:
        import librosa
        return librosa.resample(y, orig_sr=sr, target_sr=target)
    except ImportError:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(sr, target)
        return resample_poly(y, target // g, sr // g).astype(np.float32)


def _trim(y: np.ndarray, sr: int) -> np.ndarray:
    try:
        import librosa
        trimmed, _ = librosa.effects.trim(y, top_db=TRIM_TOP_DB)
        return trimmed
    except ImportError:
        frame = int(sr * 0.02)
        if len(y) < frame:
            return y
        frames = len(y) // frame
        rms = np.sqrt(np.mean(y[: frames * frame].reshape(frames, frame) ** 2, axis=1))
        thr = rms.max() * (10 ** (-TRIM_TOP_DB / 20))
        voiced = np.where(rms > thr)[0]
        if voiced.size == 0:
            return y[:0]
        return y[voiced[0] * frame: (voiced[-1] + 1) * frame]


def rms(y: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(y)))) if y.size else 0.0


def preprocess(y: np.ndarray, sr: int, enhance: bool = True) -> tuple[np.ndarray, int]:
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 2:                         # (frames, channels) → 모노
        y = y.mean(axis=1)
    y = _resample(y, sr, TARGET_SR).astype(np.float32)

    if rms(y) < SILENCE_RMS:
        raise AudioError("무음으로 판단됩니다. 마이크를 확인하고 다시 녹음해 주세요")

    if enhance:
        y = _trim(y, TARGET_SR)
        if len(y) / TARGET_SR < MIN_VOICED_SEC:
            raise AudioError("말소리 구간이 너무 짧습니다")
        peak = float(np.max(np.abs(y)))
        if peak > 0:
            y = (y / peak * 0.95).astype(np.float32)
    return y, TARGET_SR


def describe(y: np.ndarray, sr: int) -> dict:
    """선택 확장(B12)·보고서용 간단한 음향 통계. 발음 정확도 판정에 사용하지 않음."""
    return {"duration_s": round(len(y) / sr, 2), "rms": round(rms(y), 4)}
