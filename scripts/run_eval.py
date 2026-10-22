"""평가용 녹음 일괄 평가 — 전처리 전후 비교 / STT 모델 비교.

준비: data/eval/ 에 평가 녹음(WAV)을 두고, data/eval/manifest.csv 작성
      (형식은 data/eval_manifest_example.csv 참고: audio_path, reference, speaker, note)

사용법 (프로젝트 루트에서):
    # 전처리 전후 비교 (base 모델)
    python scripts/run_eval.py --compare-preprocess
    # 모델 비교 (전처리 적용)
    python scripts/run_eval.py --models base small
    # 둘 다
    python scripts/run_eval.py --models base small --compare-preprocess

출력: reports/eval_results.csv (건별), reports/eval_summary.csv (조건별 평균)
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import audio, core, stt  # noqa: E402


def evaluate_one(path: Path, reference: str, model: str, enhance: bool) -> dict:
    row = {"audio_path": str(path), "reference": reference, "model": model,
           "preprocess": "enhanced" if enhance else "raw"}
    try:
        y, sr = audio.load_and_validate(path)
        y, sr = audio.preprocess(y, sr, enhance=enhance)
        row["duration_s"] = round(len(y) / sr, 2)
        out = stt.transcribe(y, sr, model_name=model)
        m = core.compute_metrics(reference, out["text"])
        row.update(transcript=out["text"], stt_ms=out["stt_ms"], status="ok",
                   wer=m["wer"], cer=m["cer"], S=m["S"], D=m["D"], I=m["I"], N=m["N"])
    except audio.AudioError as e:
        row.update(status="invalid_audio", error=str(e))
    except stt.STTError as e:
        row.update(status="stt_failed", error=str(e))
    return row


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="data/eval/manifest.csv")
    p.add_argument("--models", nargs="+", default=["base"])
    p.add_argument("--compare-preprocess", action="store_true")
    args = p.parse_args()

    manifest = pd.read_csv(ROOT / args.manifest)
    conditions = [(m, e) for m in args.models
                  for e in ([False, True] if args.compare_preprocess else [True])]
    print(f"평가 {len(manifest)}건 × 조건 {len(conditions)}개 = {len(manifest) * len(conditions)}회")

    rows, t0 = [], time.perf_counter()
    for model, enhance in conditions:
        for r in manifest.itertuples():
            rows.append(evaluate_one(ROOT / r.audio_path, r.reference, model, enhance))
            print(f"  [{model}/{'enh' if enhance else 'raw'}] {Path(r.audio_path).name}: "
                  f"WER={rows[-1].get('wer')}")

    df = pd.DataFrame(rows)
    (ROOT / "reports").mkdir(exist_ok=True)
    df.to_csv(ROOT / "reports" / "eval_results.csv", index=False, encoding="utf-8-sig")

    ok = df[df["status"] == "ok"]
    summary = (ok.groupby(["model", "preprocess"])
                 .agg(n=("wer", "size"), wer_mean=("wer", "mean"), cer_mean=("cer", "mean"),
                      wer_median=("wer", "median"), stt_ms_mean=("stt_ms", "mean"))
                 .round(4).reset_index())
    summary.to_csv(ROOT / "reports" / "eval_summary.csv", index=False, encoding="utf-8-sig")

    print("\n=== 조건별 요약 ===")
    print(summary.to_string(index=False))
    print(f"\n실패 {len(df) - len(ok)}건 · 총 {time.perf_counter() - t0:.1f}초")
    print("→ reports/eval_results.csv, reports/eval_summary.csv 저장")


if __name__ == "__main__":
    main()
