"""audio 단위 테스트 — T06(무음·깨진 WAV) 및 표준화(모노·16kHz)."""
import io

import numpy as np
import pytest
from scipy.io import wavfile

from src.audio import AudioError, load_and_validate, preprocess


def make_wav(seconds=1.0, sr=44100, channels=1, amp=0.3, freq=220.0) -> bytes:
    t = np.arange(int(seconds * sr)) / sr
    y = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    if channels == 2:
        y = np.stack([y, y], axis=1)
    buf = io.BytesIO()
    wavfile.write(buf, sr, (y * 32767).astype(np.int16))
    return buf.getvalue()


def test_valid_stereo_44k_to_mono_16k():
    y, sr = load_and_validate(make_wav(1.0, 44100, channels=2))
    assert sr == 44100
    y2, sr2 = preprocess(y, sr, enhance=False)
    assert sr2 == 16000 and y2.ndim == 1
    assert abs(len(y2) - 16000) <= 2


def test_enhance_normalizes_peak():
    y, sr = load_and_validate(make_wav(1.0, 16000, amp=0.1))
    y2, _ = preprocess(y, sr, enhance=True)
    assert np.max(np.abs(y2)) == pytest.approx(0.95, abs=1e-3)


def test_T06_silence():
    y, sr = load_and_validate(make_wav(1.0, 16000, amp=0.0))
    with pytest.raises(AudioError, match="무음"):
        preprocess(y, sr)


def test_T06_corrupted_bytes():
    with pytest.raises(AudioError):
        load_and_validate(b"RIFF\x00\x00\x00\x00WAVEgarbage" + b"\x00" * 40)


def test_not_wav():
    with pytest.raises(AudioError, match="WAV"):
        load_and_validate(b"ID3" + b"\x00" * 100)    # mp3 헤더


def test_too_short():
    with pytest.raises(AudioError, match="짧"):
        load_and_validate(make_wav(0.2, 16000))


def test_too_long():
    with pytest.raises(AudioError, match="깁"):
        load_and_validate(make_wav(31.0, 8000))


def test_none_input():
    with pytest.raises(AudioError):
        load_and_validate(None)
