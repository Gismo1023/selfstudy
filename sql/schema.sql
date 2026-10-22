-- =========================================================
-- AI 말하기 코치 — PostgreSQL 스키마 (Neon 호환, PG13+)
-- 실행: psql "$DATABASE_URL" -f sql/schema.sql
--   또는 python scripts/seed_sentences.py --init
-- =========================================================

CREATE TABLE IF NOT EXISTS sentences (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text       TEXT NOT NULL,
    level      SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 3),  -- 1 쉬움 / 2 보통 / 3 어려움
    category   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS practice_runs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,                       -- 익명 세션 ID (로그인 없음)
    sentence_id UUID NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    transcript  TEXT,                                -- STT 전사문 (음성 원본은 저장하지 않음)
    wer         DOUBLE PRECISION,                    -- N=0 이면 NULL, 1.0 초과 허용
    cer         DOUBLE PRECISION,
    latency_ms  INTEGER,                             -- 총 처리 시간
    status      TEXT NOT NULL DEFAULT 'ok'
                CHECK (status IN ('ok', 'silent', 'invalid_audio', 'empty_transcript',
                                  'empty_reference', 'tts_failed', 'db_failed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS error_items (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID NOT NULL REFERENCES practice_runs(id) ON DELETE CASCADE,
    error_type       TEXT NOT NULL CHECK (error_type IN ('S', 'D', 'I')),
    reference_token  TEXT,                           -- I(삽입)는 NULL
    hypothesis_token TEXT,                           -- D(삭제)는 NULL
    position         INTEGER NOT NULL                -- 정답 기준 어절 인덱스
);

CREATE INDEX IF NOT EXISTS idx_runs_session  ON practice_runs (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_sentence ON practice_runs (sentence_id);
CREATE INDEX IF NOT EXISTS idx_errors_run    ON error_items (run_id);
