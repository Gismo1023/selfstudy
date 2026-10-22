"""data/sentences.csv → sentences 테이블 적재.

사용법 (프로젝트 루트에서):
    python scripts/seed_sentences.py --init   # 스키마 생성 + 적재
    python scripts/seed_sentences.py          # 적재만 (같은 id는 내용 갱신)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import get_conn, load_sentences_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="sql/schema.sql 먼저 실행")
    args = parser.parse_args()

    df = load_sentences_csv()
    with get_conn() as conn, conn.cursor() as cur:
        if args.init:
            cur.execute((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
            print("✔ 스키마 생성 완료")
        cur.executemany(
            """
            INSERT INTO sentences (id, text, level, category)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
               SET text = EXCLUDED.text, level = EXCLUDED.level, category = EXCLUDED.category
            """,
            [(r.id, r.text, int(r.level), r.category) for r in df.itertuples()],
        )
        conn.commit()
        cur.execute("SELECT level, COUNT(*) FROM sentences GROUP BY level ORDER BY level")
        print("✔ 적재 완료 (난이도별 문장 수):", dict(cur.fetchall()))


if __name__ == "__main__":
    main()
