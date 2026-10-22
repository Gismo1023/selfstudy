"""UI-03 이력 — 연습 횟수, WER/CER 추이(B09), 동일 문장 시도별 비교(B10)."""
import pandas as pd
import plotly.express as px
import streamlit as st

from src import db  # noqa: E402
from src.ui_common import init_session, pct, render_sidebar  # noqa: E402

session_id = init_session()
render_sidebar()

# db.get_history 반환 컬럼 (DB 담당과 합의)
REQUIRED = ["sentence_id", "sentence_text", "transcript", "wer", "cer",
            "latency_ms", "status", "created_at"]

st.title("📈 연습 이력")

try:
    df = db.get_history(session_id)
except Exception:
    df = pd.DataFrame()
    st.error("이력을 불러오지 못했습니다. DB 연결을 확인해 주세요.")

if df is None or df.empty:
    st.info("아직 연습 기록이 없습니다. 연습 홈에서 첫 연습을 시작해 보세요.")
    st.page_link("pages/home.py", label="연습 홈으로", icon="🏠")
    st.stop()

missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"이력 데이터 컬럼이 부족합니다: {missing} (db.get_history 확인 필요)")
    st.stop()

df["created_at"] = pd.to_datetime(df["created_at"])
df = df.sort_values("created_at").reset_index(drop=True)
df["attempt"] = df.groupby("sentence_id").cumcount() + 1
df["WER(%)"] = df["wer"] * 100
df["CER(%)"] = df["cer"] * 100

# ── KPI ──────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("총 연습 횟수", f"{len(df)}회")
k2.metric("연습한 문장 수", f"{df['sentence_id'].nunique()}개")
k3.metric("평균 WER", pct(df["wer"].mean()))
recent, first = df["wer"].tail(5).mean(), df["wer"].head(5).mean()
k4.metric("최근 5회 평균 WER", pct(recent),
          delta=f"{(recent - first) * 100:+.1f}%p" if len(df) > 5 else None,
          delta_color="inverse")

st.divider()

# ── B09 전체 추이 ────────────────────────────────────
st.subheader("전체 연습 추이")
fig_all = px.line(df, x="created_at", y=["WER(%)", "CER(%)"], markers=True,
                  labels={"created_at": "연습 시각", "value": "오류율(%)", "variable": "지표"})
st.plotly_chart(fig_all, use_container_width=True)

# ── B10 동일 문장 시도별 비교 ────────────────────────
st.subheader("문장별 재연습 비교")
counts = df.groupby(["sentence_id", "sentence_text"]).size().reset_index(name="n")
counts = counts.sort_values("n", ascending=False)
options = counts.to_dict("records")
picked = st.selectbox("문장 선택", options,
                      format_func=lambda r: f"{r['sentence_text']}  ({r['n']}회)")

one = df[df["sentence_id"] == picked["sentence_id"]]
if len(one) < 2:
    st.caption("같은 문장을 2회 이상 연습하면 시도별 변화를 비교할 수 있습니다.")
fig_one = px.line(one, x="attempt", y=["WER(%)", "CER(%)"], markers=True,
                  labels={"attempt": "시도 회차", "value": "오류율(%)", "variable": "지표"})
fig_one.update_xaxes(dtick=1)
st.plotly_chart(fig_one, use_container_width=True)

st.dataframe(
    one[["attempt", "transcript", "WER(%)", "CER(%)", "latency_ms", "created_at"]]
    .rename(columns={"attempt": "회차", "transcript": "전사 결과",
                     "latency_ms": "처리시간(ms)", "created_at": "시각"}),
    hide_index=True, use_container_width=True,
    column_config={"WER(%)": st.column_config.NumberColumn(format="%.1f"),
                   "CER(%)": st.column_config.NumberColumn(format="%.1f")},
)

# ── 전체 기록 ────────────────────────────────────────
with st.expander("전체 기록 보기"):
    st.dataframe(
        df[["created_at", "sentence_text", "transcript", "WER(%)", "CER(%)", "status"]]
        .sort_values("created_at", ascending=False),
        hide_index=True, use_container_width=True,
    )
