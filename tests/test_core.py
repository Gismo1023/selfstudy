"""core 단위 테스트 — 수락 테스트 T01~T04, T07 + 수작업 검증 10건.

실행: pytest tests/ -v
CER은 공백 제외 문자 기준. 각 케이스 주석에 손으로 계산한 근거를 적었습니다.
"""
import pytest

from src.core import align, compute_metrics, make_feedback, normalize

# (이름, 정답, 전사, 기대 WER, 기대 CER, 기대 (S, D, I) — 어절 기준)
HAND_CASES = [
    # 1) T01 동일: 오류 0
    ("T01_identical", "오늘은 날씨가 정말 좋습니다", "오늘은 날씨가 정말 좋습니다", 0.0, 0.0, (0, 0, 0)),
    # 2) T02 '정말' 누락: WER 1/4 · CER 2/12 (오늘은3+날씨가3+정말2+좋습니다4=12, '정','말' 삭제)
    ("T02_deletion", "오늘은 날씨가 정말 좋습니다", "오늘은 날씨가 좋습니다", 1 / 4, 2 / 12, (0, 1, 0)),
    # 3) T03 '정말' 추가: WER 1/3 · CER 2/10
    ("T03_insertion", "오늘은 날씨가 좋습니다", "오늘은 날씨가 정말 좋습니다", 1 / 3, 2 / 10, (0, 0, 1)),
    # 4) T04 대체: 먹었습니다→먹었어요 WER 1/2 · CER 3/8 (습→어, 니→요 대체 + 다 삭제)
    ("T04_substitution", "사과를 먹었습니다", "사과를 먹었어요", 1 / 2, 3 / 8, (1, 0, 0)),
    # 5) T07 빈 전사: 전부 삭제 WER 1/1 · CER 5/5
    ("T07_empty_hyp", "안녕하세요", "", 1.0, 1.0, (0, 1, 0)),
    # 6) 100% 초과 허용: 정답 1어절에 2어절 삽입 WER 2/1 · CER 10/1
    ("over_100pct", "네", "네 알겠습니다 감사합니다", 2.0, 10.0, (0, 0, 2)),
    # 7) 문장부호·연속 공백은 정규화로 제거 → 오류 0
    ("punct_normalize", "오늘은 날씨가, 정말 좋습니다!", "오늘은   날씨가 정말 좋습니다.", 0.0, 0.0, (0, 0, 0)),
    # 8) 띄어쓰기 차이: 어절은 2/3 (S+D), 문자는 공백 제외라 0
    ("spacing_only", "할 수 있습니다", "할수 있습니다", 2 / 3, 0.0, (1, 1, 0)),
    # 9) 숫자 미변환 정책: '3개'→'세 개' 어절 S+I 2/3, 문자 '3'→'세' 1/7
    ("number_policy", "사과 3개 주세요", "사과 세 개 주세요", 2 / 3, 1 / 7, (1, 0, 1)),
    # 10) 복합: 어절 하나 대체 + 끝 어절 누락
    #     정답 4어절 [내가, 그린, 기린, 그림] / 전사 [내가, 그린, 기름]
    #     어절: 기린→기름 대체 1 + 그림 삭제 1 = 2/4
    #     문자: 내가그린기린그림(8) vs 내가그린기름(6) → 린→름 대체, 그·림 삭제 = 3/8
    ("mixed", "내가 그린 기린 그림", "내가 그린 기름", 2 / 4, 3 / 8, (1, 1, 0)),
]


@pytest.mark.parametrize("name,ref,hyp,wer,cer,sdi", HAND_CASES, ids=[c[0] for c in HAND_CASES])
def test_hand_verified(name, ref, hyp, wer, cer, sdi):
    m = compute_metrics(ref, hyp)
    assert m["wer"] == pytest.approx(wer)
    assert m["cer"] == pytest.approx(cer)
    assert (m["S"], m["D"], m["I"]) == sdi


def test_T02_deletion_position():
    errors = align("오늘은 날씨가 정말 좋습니다", "오늘은 날씨가 좋습니다")
    assert len(errors) == 1
    e = errors[0]
    assert (e.error_type, e.reference_token, e.hypothesis_token, e.position) == ("D", "정말", None, 2)


def test_T03_insertion_position():
    (e,) = align("오늘은 날씨가 좋습니다", "오늘은 날씨가 정말 좋습니다")
    assert (e.error_type, e.hypothesis_token, e.position) == ("I", "정말", 2)


def test_T04_substitution_tokens():
    (e,) = align("사과를 먹었습니다", "사과를 먹었어요")
    assert (e.error_type, e.reference_token, e.hypothesis_token, e.position) == ("S", "먹었습니다", "먹었어요", 1)


def test_insertion_at_end_position():
    (e,) = align("밥 먹었어요", "밥 먹었어요 정말")
    assert e.error_type == "I" and e.position == 2   # = len(정답 어절)


def test_N_zero_returns_none():
    m = compute_metrics("", "아무 말")
    assert m["wer"] is None and m["cer"] is None and m["N"] == 0


def test_empty_both():
    m = compute_metrics("", "")
    assert m["wer"] is None and align("", "") == []


def test_normalize_idempotent():
    s = "  안녕하세요,   반갑습니다!!  "
    assert normalize(s) == "안녕하세요 반갑습니다"
    assert normalize(normalize(s)) == normalize(s)


def test_matches_jiwer_if_installed():
    jiwer = pytest.importorskip("jiwer")
    for _, ref, hyp, *_ in HAND_CASES:
        if not normalize(ref) or not normalize(hyp):
            continue
        assert compute_metrics(ref, hyp)["wer"] == pytest.approx(jiwer.wer(normalize(ref), normalize(hyp)))


# ── 피드백 ────────────────────────────────────────────
def test_feedback_deletion_josa():
    fb = make_feedback(align("오늘은 날씨가 정말 좋습니다", "오늘은 날씨가 좋습니다"))
    assert "‘정말’이 누락된 것으로 인식되었습니다" in fb
    assert fb.endswith("정답을 듣고 다시 말해 보세요.")


def test_feedback_substitution_josa():
    fb = make_feedback(align("사과를 먹었습니다", "사과를 먹었어요"))
    assert "‘먹었습니다’가 ‘먹었어요’로 다르게 인식되었습니다" in fb


def test_feedback_insertion():
    fb = make_feedback(align("밥 먹었어요", "밥 많이 먹었어요"))
    assert "정답에 없는 ‘많이’가 추가로 인식되었습니다" in fb


def test_feedback_perfect():
    assert "일치" in make_feedback([])


def test_feedback_all_missing():
    errors = align("안녕하세요 반갑습니다", "")
    assert "인식되지 않았습니다" in make_feedback(errors, n_ref=2)


def test_feedback_truncates():
    errors = align("가 나 다 라 마", "")
    fb = make_feedback(errors, n_ref=None, max_items=3)
    assert "그 밖에 2건" in fb
