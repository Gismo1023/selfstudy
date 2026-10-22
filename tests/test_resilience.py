"""장애 대응 테스트 — T08(TTS 실패), T09(DB 장애). 네트워크·DB 없이 실행됩니다."""
import pytest

from src import db, tts
from src.core import compute_metrics


@pytest.fixture
def broken_db(monkeypatch):
    # 닫힌 로컬 포트 → 즉시 연결 거부
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")


def test_T09_list_sentences_falls_back_to_csv(broken_db):
    df = db.list_sentences()
    assert len(df) >= 30
    assert set(df["level"]) == {1, 2, 3}
    assert {"id", "text", "level", "category"} <= set(df.columns)


def test_T09_save_run_returns_none(broken_db):
    run_id = db.save_run("sess", "00000000-0000-0000-0000-000000000000", "텍스트",
                         compute_metrics("가 나", "가"), 100, "ok", [])
    assert run_id is None


def test_T09_get_history_raises_dberror(broken_db):
    with pytest.raises(db.DBError):
        db.get_history("sess")


def test_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(db.DBError):
        db.get_conn()


def test_T08_tts_failure_returns_none(monkeypatch, tmp_path):
    async def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(tts, "_synthesize_async", boom)
    monkeypatch.setattr(tts, "FALLBACK_DIR", tmp_path)
    assert tts.synthesize("안녕하세요") is None


def test_T08_tts_uses_fallback_file(monkeypatch, tmp_path):
    async def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(tts, "_synthesize_async", boom)
    monkeypatch.setattr(tts, "FALLBACK_DIR", tmp_path)
    tts.fallback_path("안녕하세요").write_bytes(b"ID3fake")
    assert tts.synthesize("안녕하세요") == b"ID3fake"


def test_tts_empty_text():
    assert tts.synthesize("   ") is None


def test_sentence_csv_ids_unique():
    df = db.load_sentences_csv()
    assert df["id"].is_unique and df["text"].is_unique
    assert (df.groupby("level").size() >= 10).all()
