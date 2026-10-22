"""핵심 평가 알고리즘 — 정규화, Levenshtein 정렬, WER/CER, 피드백 생성.

정책(설계서 2-1과 동일, 정답·전사에 같은 규칙 적용):
  - 공백: 양끝 제거, 연속 공백 → 1칸
  - 문장부호: . , ? ! ~ … " ' 등 제거
  - 숫자: 변환하지 않음 ("3개" ≠ "세 개" → 오류로 집계)
  - WER: 공백 기준 어절 단위
  - CER: 공백 제외 문자(음절) 단위
  - (S + D + I) / N, N = 정답 토큰 수. N = 0 이면 None. 100% 초과 값을 자르지 않음.

주의: 이 지표는 'STT 전사 일치도'이며 실제 발음 정확도를 판정하지 않습니다.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal, Optional

ErrorType = Literal["S", "D", "I"]

_PUNCT_RE = re.compile(r"[.,?!~…·\"'“”‘’()\[\]{}:;\-]")
_SPACE_RE = re.compile(r"\s+")


@dataclass
class ErrorItem:
    error_type: ErrorType            # S=대체, D=삭제(누락), I=삽입(추가)
    reference_token: Optional[str]   # 정답 토큰 (I는 None)
    hypothesis_token: Optional[str]  # 전사 토큰 (D는 None)
    position: int                    # 정답 기준 토큰 인덱스. I는 '이 토큰 앞'에 끼어든 위치

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------
# 1. 정규화·토큰화
# ---------------------------------------------------------------
def normalize(text: str | None) -> str:
    """정답·전사 공통 정규화. 여러 번 적용해도 결과가 같음(idempotent)."""
    if not text:
        return ""
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text)
    return text.strip()


def tokenize(text: str, unit: str = "word") -> list[str]:
    """unit='word' → 공백 기준 어절, unit='char' → 공백 제외 문자."""
    text = normalize(text)
    if unit == "word":
        return text.split() if text else []
    if unit == "char":
        return list(text.replace(" ", ""))
    raise ValueError("unit은 'word' 또는 'char'만 가능합니다")


# ---------------------------------------------------------------
# 2. Levenshtein 동적 계획법 정렬
# ---------------------------------------------------------------
def _edit_table(ref: list[str], hyp: list[str]) -> list[list[int]]:
    """dp[i][j] = ref[:i] 를 hyp[:j] 로 바꾸는 최소 편집 횟수."""
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i                      # 전부 삭제
    for j in range(m + 1):
        dp[0][j] = j                      # 전부 삽입
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j - 1] + cost,  # 일치 / 대체
                dp[i - 1][j] + 1,         # 삭제
                dp[i][j - 1] + 1,         # 삽입
            )
    return dp


def align_tokens(ref: list[str], hyp: list[str]) -> list[ErrorItem]:
    """토큰 리스트를 정렬하여 오류 항목만 정답 순서대로 반환.

    역추적 우선순위: 일치 → 대체 → 삭제 → 삽입 (동점 시 결정 규칙)
    """
    dp = _edit_table(ref, hyp)
    i, j = len(ref), len(hyp)
    errors: list[ErrorItem] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            i, j = i - 1, j - 1                                   # 일치
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            errors.append(ErrorItem("S", ref[i - 1], hyp[j - 1], i - 1))
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            errors.append(ErrorItem("D", ref[i - 1], None, i - 1))
            i -= 1
        else:
            errors.append(ErrorItem("I", None, hyp[j - 1], i))
            j -= 1
    errors.reverse()
    return errors


def align(ref: str, hyp: str, unit: str = "word") -> list[ErrorItem]:
    """문자열 정답·전사를 정규화 후 정렬. 빈 전사 → 전체 삭제(D)."""
    return align_tokens(tokenize(ref, unit), tokenize(hyp, unit))


# ---------------------------------------------------------------
# 3. WER / CER
# ---------------------------------------------------------------
def _rate(errors: list[ErrorItem], n: int) -> tuple[Optional[float], int, int, int]:
    s = sum(e.error_type == "S" for e in errors)
    d = sum(e.error_type == "D" for e in errors)
    ins = sum(e.error_type == "I" for e in errors)
    rate = None if n == 0 else (s + d + ins) / n
    return rate, s, d, ins


def compute_metrics(ref: str, hyp: str) -> dict:
    """WER(어절)·CER(문자) 및 S/D/I/N 반환.

    반환 예: {"wer": 0.25, "cer": 0.1667, "S": 0, "D": 1, "I": 0, "N": 4,
             "cer_S": 0, "cer_D": 2, "cer_I": 0, "N_char": 12}
    N = 0 이면 wer/cer = None (분모 0 처리).
    """
    ref_w, hyp_w = tokenize(ref, "word"), tokenize(hyp, "word")
    ref_c, hyp_c = tokenize(ref, "char"), tokenize(hyp, "char")

    wer, s, d, i = _rate(align_tokens(ref_w, hyp_w), len(ref_w))
    cer, cs, cd, ci = _rate(align_tokens(ref_c, hyp_c), len(ref_c))
    return {
        "wer": wer, "cer": cer,
        "S": s, "D": d, "I": i, "N": len(ref_w),
        "cer_S": cs, "cer_D": cd, "cer_I": ci, "N_char": len(ref_c),
    }


# ---------------------------------------------------------------
# 4. 피드백 문구 (전사 기반 — 발음 오류라고 단정하지 않음)
# ---------------------------------------------------------------
def _has_batchim(word: str) -> bool:
    if not word:
        return False
    ch = word[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    if ch.isdigit():                      # 0 영, 1 일, 3 삼, 6 육, 7 칠, 8 팔 → 받침
        return ch in "013678"
    return False


def _is_rieul(word: str) -> bool:
    ch = word[-1] if word else ""
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 8


def _i_ga(word: str) -> str:
    return f"‘{word}’{'이' if _has_batchim(word) else '가'}"


def _euro(word: str) -> str:
    use_euro = _has_batchim(word) and not _is_rieul(word)
    return f"‘{word}’{'으로' if use_euro else '로'}"


def make_feedback(errors: list, n_ref: Optional[int] = None, max_items: int = 3) -> str:
    """오류 목록 → 재연습 안내 문장.

    예) "‘정말’이 누락된 것으로 인식되었습니다. 정답을 듣고 다시 말해 보세요."
    """
    def g(e, k):
        return e.get(k) if isinstance(e, dict) else getattr(e, k)

    if not errors:
        return "정답과 일치하게 전사되었습니다. 잘하셨어요!"

    if n_ref and all(g(e, "error_type") == "D" for e in errors) and len(errors) == n_ref:
        return "음성이 인식되지 않았습니다. 정답을 듣고 조금 더 또렷하게 다시 말해 보세요."

    lines = []
    for e in errors[:max_items]:
        t, ref, hyp = g(e, "error_type"), g(e, "reference_token"), g(e, "hypothesis_token")
        if t == "D":
            lines.append(f"{_i_ga(ref)} 누락된 것으로 인식되었습니다.")
        elif t == "S":
            lines.append(f"{_i_ga(ref)} {_euro(hyp)} 다르게 인식되었습니다.")
        else:
            lines.append(f"정답에 없는 {_i_ga(hyp)} 추가로 인식되었습니다.")
    rest = len(errors) - max_items
    if rest > 0:
        lines.append(f"그 밖에 {rest}건의 차이가 더 있습니다.")
    lines.append("정답을 듣고 다시 말해 보세요.")
    return " ".join(lines)
