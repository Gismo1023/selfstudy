"""시연용 TTS 폴백 음성 사전 생성 (네트워크 장애 대비).

난이도별 앞 문장들의 정답 음성을 assets/tts_fallback/ 에 MP3로 저장합니다.
edge-tts 합성음이므로 커밋해도 개인정보 문제는 없습니다.

사용법:  python scripts/make_tts_fallback.py --per-level 2
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import load_sentences_csv  # noqa: E402
from src.tts import save_fallback  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--per-level", type=int, default=2)
    args = p.parse_args()

    df = load_sentences_csv()
    texts = df.groupby("level").head(args.per_level)["text"].tolist()
    texts.append("정답과 일치하게 전사되었습니다. 잘하셨어요!")
    for t in texts:
        path = save_fallback(t)
        print(("✔ " if path else "✘ ") + t)


if __name__ == "__main__":
    main()
