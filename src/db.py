"""DB 접근 — PostgreSQL(Neon). 모든 SQL은 파라미터 바인딩(%s) 사용.

장애 정책
  - list_sentences : DB 실패 시 data/sentences.csv 로 폴백
  - save_run       : 실패 시 None 반환 (앱 중단 금지, UI가 경고 표시)
  - get_history / get_dashboard_stats : 실패 시 DBError 발생 → UI가 안내 문구 표시
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[1]
SENTENCES_CSV = ROOT / "data" / "sentences.csv"
log = logging.getLogger(__name__)


class DBError(Exception):
    """DB 연결·조회 실패."""


def _database_url() -> str | None:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    try:  # Streamlit Cloud secrets
        import streamlit as st
        return st.secrets.get("DATABASE_URL")
    except Exception:
        return None


def get_conn():
    url = _database_url()
    if not url:
        raise DBError("DATABASE_URL이 설정되지 않았습니다(.env 확인)")
    try:
        import psycopg
        return psycopg.connect(url, connect_timeout=5)
    except Exception as exc:
        raise DBError(f"DB 연결 실패: {type(exc).__name__}") from exc


def _query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# ---------------------------------------------------------------
# 문장
# ---------------------------------------------------------------
def load_sentences_csv(level: int | None = None) -> pd.DataFrame:
    df = pd.read_csv(SENTENCES_CSV, dtype={"id": str}, encoding="utf-8-sig")
    if level is not None:
        df = df[df["level"] == level]
    return df.reset_index(drop=True)


def list_sentences(level: int | None = None) -> pd.DataFrame:
    """columns: id(str), text, level, category"""
    try:
        sql = "SELECT id::text AS id, text, level, category FROM sentences"
        params: tuple = ()
        if level is not None:
            sql += " WHERE level = %s"
            params = (level,)
        df = _query_df(sql + " ORDER BY level, text", params)
        if not df.empty:
            return df
    except Exception as exc:
        log.warning("문장 DB 조회 실패 → CSV 폴백: %s", exc)
    return load_sentences_csv(level)


# ---------------------------------------------------------------
# 연습 결과 저장
# ---------------------------------------------------------------
def _g(e, k):
    return e.get(k) if isinstance(e, dict) else getattr(e, k)


def save_run(session_id: str, sentence_id: str, transcript: str, metrics: dict,
             latency_ms: int, status: str, errors: list) -> str | None:
    """practice_runs 1건 + error_items N건 저장 → run_id(str). 실패 시 None."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO practice_runs
                        (session_id, sentence_id, transcript, wer, cer, latency_ms, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id::text
                    """,
                    (session_id, sentence_id, transcript, metrics.get("wer"),
                     metrics.get("cer"), latency_ms, status),
                )
                run_id = cur.fetchone()[0]
                if errors:
                    cur.executemany(
                        """
                        INSERT INTO error_items
                            (run_id, error_type, reference_token, hypothesis_token, position)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [(run_id, _g(e, "error_type"), _g(e, "reference_token"),
                          _g(e, "hypothesis_token"), _g(e, "position")) for e in errors],
                    )
            conn.commit()
        return run_id
    except Exception as exc:
        log.error("연습 결과 저장 실패: %s", type(exc).__name__)
        return None


# ---------------------------------------------------------------
# 조회
# ---------------------------------------------------------------
def get_history(session_id: str, sentence_id: str | None = None) -> pd.DataFrame:
    """columns: run_id, sentence_id, sentence_text, level, transcript, wer, cer,
                latency_ms, status, created_at"""
    sql = """
        SELECT r.id::text AS run_id, r.sentence_id::text AS sentence_id,
               s.text AS sentence_text, s.level, r.transcript, r.wer, r.cer,
               r.latency_ms, r.status, r.created_at
        FROM practice_runs r
        JOIN sentences s ON s.id = r.sentence_id
        WHERE r.session_id = %s
    """
    params: tuple = (session_id,)
    if sentence_id:
        sql += " AND r.sentence_id = %s"
        params += (sentence_id,)
    try:
        return _query_df(sql + " ORDER BY r.created_at", params)
    except DBError:
        raise
    except Exception as exc:
        raise DBError(f"이력 조회 실패: {type(exc).__name__}") from exc


def get_dashboard_stats(session_id: str | None = None) -> dict[str, pd.DataFrame]:
    """오류 유형 빈도 + 난이도별 평균 WER/CER. session_id=None 이면 전체."""
    where, params = ("WHERE r.session_id = %s", (session_id,)) if session_id else ("", ())
    try:
        errors = _query_df(f"""
            SELECT e.error_type, COUNT(*) AS count
            FROM error_items e JOIN practice_runs r ON r.id = e.run_id
            {where}
            GROUP BY e.error_type ORDER BY e.error_type
        """, params)
        by_level = _query_df(f"""
            SELECT s.level, COUNT(*) AS runs, AVG(r.wer) AS avg_wer, AVG(r.cer) AS avg_cer
            FROM practice_runs r JOIN sentences s ON s.id = r.sentence_id
            {where}
            GROUP BY s.level ORDER BY s.level
        """, params)
        top_missed = _query_df(f"""
            SELECT e.reference_token AS token, COUNT(*) AS count
            FROM error_items e JOIN practice_runs r ON r.id = e.run_id
            {where + (' AND' if where else 'WHERE')} e.error_type IN ('D', 'S')
            GROUP BY e.reference_token ORDER BY count DESC LIMIT 10
        """, params)
        return {"errors": errors, "by_level": by_level, "top_missed": top_missed}
    except DBError:
        raise
    except Exception as exc:
        raise DBError(f"통계 조회 실패: {type(exc).__name__}") from exc
