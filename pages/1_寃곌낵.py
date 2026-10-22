"""UI-02 결과 — 정답/전사 비교, 오류 강조, WER/CER, 피드백 음성."""
from html import escape

import streamlit as st

st.set_page_config(page_title="결과 | AI 말하기 코치", page_icon="📝", layout="wide")

from src.ui_common import get_attr, pct, render_sidebar, speak  # noqa: E402

render_sidebar()

res = st.session_state.get("last_result")
if not res:
    st.info("아직 분석 결과가 없습니다. 연습 홈에서 먼저 녹음해 주세요.")
    st.page_link("app.py", label="연습 홈으로", icon="🏠")
    st.stop()

STYLE = """
<style>
.diff {font-size:1.35rem; line-height:2.4rem;}
.tok {padding:2px 6px; margin:0 2px; border-radius:6px;}
.ok  {background:rgba(46,160,67,.15);}
.del {background:rgba(248,81,73,.18); text-decoration:line-through; color:#d1242f;}
.sub {background:rgba(251,143,68,.22);}
.ins {background:rgba(56,139,253,.20); color:#0969da;}
.legend span {margin-right:14px; font-size:.85rem;}
</style>
"""


def render_diff(reference: str, errors) -> str:
    """정답 어절 기준으로 오류를 색상 표시.

    가정(core.align 담당과 합의 필요):
      - position = 정답 기준 어절 인덱스
      - 삽입(I)의 position = 그 어절 '앞'에 끼어든 위치 (끝 삽입은 len(ref))
    """
    ref_tokens = reference.split()
    by_pos, inserts = {}, {}
    for e in errors:
        etype = get_attr(e, "error_type")
        pos = get_attr(e, "position")
        if etype == "I":
            inserts.setdefault(pos, []).append(e)
        else:
            by_pos[pos] = e

    def ins_html(pos):
        return "".join(
            f'<span class="tok ins">+{escape(get_attr(e, "hypothesis_token") or "")}</span>'
            for e in inserts.get(pos, [])
        )

    parts = []
    for i, tok in enumerate(ref_tokens):
        parts.append(ins_html(i))
        e = by_pos.get(i)
        if e is None:
            parts.append(f'<span class="tok ok">{escape(tok)}</span>')
        elif get_attr(e, "error_type") == "D":
            parts.append(f'<span class="tok del">{escape(tok)}</span>')
        else:  # S
            hyp = escape(get_attr(e, "hypothesis_token") or "")
            parts.append(f'<span class="tok sub">{escape(tok)} → <b>{hyp}</b></span>')
    parts.append(ins_html(len(ref_tokens)))
    return f'<div class="diff">{"".join(parts)}</div>'


# ---------------------------------------------------------------
st.title("📝 분석 결과")

if res["status"] == "empty_transcript":
    st.warning("음성이 인식되지 않았습니다. 조용한 곳에서 조금 더 크게 다시 말해 보세요.")
if res["run_id"] is None:
    st.warning("이력 저장에 실패했습니다. 결과는 확인할 수 있지만 이력 화면에는 표시되지 않습니다.")

# ── 정답 vs 전사 ─────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    st.markdown("**정답 문장**")
    st.markdown(f"### {res['sentence']['text']}")
with c2:
    st.markdown("**STT 전사 결과**")
    st.markdown(f"### {res['transcript'] or '(인식된 내용 없음)'}")

st.markdown("**어절별 비교**")
st.markdown(STYLE + render_diff(res["reference"], res["errors"]), unsafe_allow_html=True)
st.markdown(
    '<div class="legend"><span class="tok ok">일치</span>'
    '<span class="tok del">누락(삭제)</span>'
    '<span class="tok sub">다르게 인식(대체)</span>'
    '<span class="tok ins">+추가(삽입)</span></div>',
    unsafe_allow_html=True,
)

st.divider()

# ── 지표 ─────────────────────────────────────────────
m = res["metrics"]
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("WER (어절)", pct(m.get("wer")))
k2.metric("CER (문자)", pct(m.get("cer")))
k3.metric("대체 S", m.get("S", 0))
k4.metric("삭제 D", m.get("D", 0))
k5.metric("삽입 I", m.get("I", 0))
st.caption("WER/CER = (S + D + I) / N · 값이 낮을수록 전사가 정답과 일치합니다. 실제 발음 정확도를 의미하지 않습니다.")

st.divider()

# ── 피드백 + 음성 ────────────────────────────────────
st.subheader("💬 피드백")
st.info(res["feedback"])

a1, a2 = st.columns(2)
with a1:
    st.markdown("**피드백 듣기**")
    if res["feedback_audio"]:
        st.audio(res["feedback_audio"], format="audio/mp3")
    else:
        st.warning("피드백 음성을 생성하지 못했습니다.")
        if st.button("🔄 음성 다시 생성"):
            res["feedback_audio"] = speak(res["feedback"])
            st.rerun()
with a2:
    st.markdown("**정답 다시 듣기**")
    answer_audio = speak(res["sentence"]["text"])
    if answer_audio:
        st.audio(answer_audio, format="audio/mp3")
    else:
        st.caption("정답 음성을 불러오지 못했습니다.")

# ── 처리 시간 ────────────────────────────────────────
t = res["timings"]
st.caption(
    f"⏱️ 전처리 {t['audio_ms']}ms · STT {t['stt_ms']}ms · 평가 {t['core_ms']}ms · "
    f"TTS {t['tts_ms']}ms · **총 {t['total_ms']}ms**"
)

st.divider()
b1, b2 = st.columns(2)
if b1.button("🔁 같은 문장 다시 연습", type="primary", use_container_width=True):
    st.session_state.retry_sentence_id = res["sentence"]["id"]
    st.switch_page("app.py")
if b2.button("📈 연습 이력 보기", use_container_width=True):
    st.switch_page("pages/2_이력.py")
