"""UI-04 분석 대시보드 (선택) — 오류 유형 빈도, 난이도별 전사 일치도, 평가 실험 결과."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src import db  # noqa: E402
from src.ui_common import LEVEL_NAMES, init_session, render_sidebar  # noqa: E402

session_id = init_session()
render_sidebar()

ERROR_NAMES = {"S": "대체", "D": "삭제(누락)", "I": "삽입(추가)"}
EVAL_SUMMARY = Path(__file__).resolve().parents[1] / "reports" / "eval_summary.csv"

st.title("📊 분석 대시보드")
scope = st.radio("범위", ["내 세션", "전체 사용자"], horizontal=True)

# ── 1. 연습 데이터 통계 ──────────────────────────────
try:
    stats = db.get_dashboard_stats(session_id if scope == "내 세션" else None)
except Exception:
    stats = None
    st.error("통계를 불러오지 못했습니다. DB 연결을 확인해 주세요.")

if stats is not None:
    if stats["by_level"].empty:
        st.info("아직 연습 기록이 없습니다.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("오류 유형 빈도")
            e = stats["errors"].assign(유형=lambda d: d["error_type"].map(ERROR_NAMES))
            st.plotly_chart(px.bar(e, x="유형", y="count", labels={"count": "건수"}),
                            use_container_width=True)
        with c2:
            st.subheader("난이도별 평균 전사 오류율")
            lv = stats["by_level"].assign(
                난이도=lambda d: d["level"].map(LEVEL_NAMES),
                **{"WER(%)": lambda d: d["avg_wer"].astype(float) * 100,
                   "CER(%)": lambda d: d["avg_cer"].astype(float) * 100})
            st.plotly_chart(px.bar(lv, x="난이도", y=["WER(%)", "CER(%)"], barmode="group",
                                   labels={"value": "오류율(%)", "variable": "지표"}),
                            use_container_width=True)

        st.subheader("자주 누락·다르게 인식된 어절 Top 10")
        st.dataframe(stats["top_missed"].rename(columns={"token": "정답 어절", "count": "건수"}),
                     hide_index=True, use_container_width=True)

st.divider()

# ── 2. 평가 실험 결과 (scripts/run_eval.py 산출물) ────
st.subheader("평가 실험: 전처리 전후 · 모델 비교")
if EVAL_SUMMARY.exists():
    summary = pd.read_csv(EVAL_SUMMARY)
    summary["조건"] = summary["model"] + " / " + summary["preprocess"]
    st.plotly_chart(
        px.bar(summary, x="조건", y=["wer_mean", "cer_mean"], barmode="group",
               labels={"value": "평균 오류율", "variable": "지표"}),
        use_container_width=True)
    st.dataframe(summary, hide_index=True, use_container_width=True)
else:
    st.info("평가 결과가 없습니다. `python scripts/run_eval.py --compare-preprocess` 실행 후 확인하세요.")

st.caption("WER/CER는 STT 전사 일치도이며 실제 발음 정확도를 판정하지 않습니다.")
