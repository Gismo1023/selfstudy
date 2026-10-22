"""TTS — edge-tts 한국어 음성 합성 (인터넷 필요).

synthesize(text, voice) → MP3 bytes | None
  1) edge-tts 호출 (최대 2회: 1회 재시도)
  2) 실패 시 assets/tts_fallback/<md5>.mp3 사전 생성 파일 사용
  3) 그래도 없으면 None → UI는 텍스트 피드백 유지 + 재시도 버튼
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import logging
from pathlib import Path

DEFAULT_VOICE = "ko-KR-SunHiNeural"
TIMEOUT_SEC = 15
FALLBACK_DIR = Path(__file__).resolve().parents[1] / "assets" / "tts_fallback"

log = logging.getLogger(__name__)


def fallback_path(text: str, voice: str = DEFAULT_VOICE) -> Path:
    key = hashlib.md5(f"{voice}|{text}".encode("utf-8")).hexdigest()
    return FALLBACK_DIR / f"{key}.mp3"


async def _synthesize_async(text: str, voice: str, rate: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        raise RuntimeError("TTS 응답에 오디오가 없습니다")
    return b"".join(chunks)


def _run(coro):
    """이벤트 루프가 이미 돌고 있으면 별도 스레드에서 실행."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def synthesize(text: str, voice: str = DEFAULT_VOICE, rate: str = "+0%",
               retries: int = 1) -> bytes | None:
    if not text or not text.strip():
        return None
    for attempt in range(retries + 1):
        try:
            return _run(asyncio.wait_for(_synthesize_async(text, voice, rate), TIMEOUT_SEC))
        except Exception as exc:
            log.warning("TTS 실패(%d/%d): %s", attempt + 1, retries + 1, type(exc).__name__)
    fb = fallback_path(text, voice)
    if fb.exists():
        return fb.read_bytes()
    return None


def save_fallback(text: str, voice: str = DEFAULT_VOICE) -> Path | None:
    """네트워크가 될 때 미리 음성을 만들어 두는 함수 (scripts/make_tts_fallback.py에서 사용)."""
    audio = synthesize(text, voice)
    if audio is None:
        return None
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    path = fallback_path(text, voice)
    path.write_bytes(audio)
    return path
