"""Storage layer.

Postgres when DATABASE_URL is set (Railway), SQLite otherwise (local/tests).

Rows are plain tuples on both backends. SQL is written with `?` placeholders and
translated to `%s` for Postgres, so the rest of the code is backend-agnostic.
"""

import hashlib
import threading
import os
import sqlite3

BOSSES = {'butterfly', 'owl', 'emma', 'demon_of_hatred', 'gyoubu', 'isshin', 'divine_dragon', 'monkeys', 'corrupted_monk', 'ape', 'true_monk', 'isshin_ashina', 'genichiro', 'headless_ape'}

BOSS_ALIASES = {'headless': 'headless_ape', 'monk': 'corrupted_monk', 'truemonk': 'true_monk', 'dragon': 'divine_dragon', 'hatred': 'demon_of_hatred'}

_COLS = """
  ts          {bigint} NOT NULL,          -- server time, unix seconds
  device      TEXT    NOT NULL,          -- HMAC of anonymous visitor ID; no raw IP
  boss        TEXT    NOT NULL,
  heals       INTEGER NOT NULL,
  revives     INTEGER NOT NULL,
  charmless   INTEGER NOT NULL,
  bell        INTEGER NOT NULL,
  prosthetic  INTEGER NOT NULL,
  art         INTEGER NOT NULL,
  score       INTEGER NOT NULL,          -- computed server-side
  excluded    INTEGER NOT NULL DEFAULT 0, -- 1 = left out of percentile stats
  flag_reason TEXT                        -- 'duplicate' | 'ml' | 'manual'
"""
_SQLITE = [
    "CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY AUTOINCREMENT,"
    + _COLS.format(bigint="INTEGER")
    + ")"
]
_PG = [
    "CREATE TABLE IF NOT EXISTS submissions (id BIGSERIAL PRIMARY KEY,"
    + _COLS.format(bigint="BIGINT")
    + ")"
]
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sub_device ON submissions(device, ts)",
    "CREATE INDEX IF NOT EXISTS idx_sub_cohort "
    "ON submissions(boss, charmless, bell, excluded, score)",
]
_initialised: set = set()
_schema_lock = threading.Lock()


def is_production():
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or
                os.environ.get("RAILWAY_ENVIRONMENT_ID") or
                os.environ.get("APP_ENV") == "production")


def lock_submission(conn, device):
    if conn.pg:
        key = int.from_bytes(hashlib.sha256(device.encode()).digest()[:8], "big", signed=True)
        conn.execute("SELECT pg_advisory_xact_lock(?)", (key,))
    else:
        conn.execute("BEGIN IMMEDIATE")


def score_of(heals: int, revives: int) -> int:
    """Same formula as scoring.mjs (prototype rules v0.1)."""
    return max(0, 100 - heals * 5 - revives * 15)


class Conn:
    def __init__(self, raw, pg: bool):
        self.raw, self.pg = raw, pg

    def execute(self, sql, params=()):
        if self.pg:
            sql = sql.replace("?", "%s")
        cur = self.raw.cursor()
        cur.execute(sql, tuple(params))
        return cur

    def executemany(self, sql, seq):
        if self.pg:
            sql = sql.replace("?", "%s")
        cur = self.raw.cursor()
        cur.executemany(sql, [tuple(p) for p in seq])
        return cur

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def connect(target=None) -> Conn:
    """target: sqlite file path, or None -> DATABASE_URL (Postgres) / DB_PATH (SQLite)."""
    url = None if target else os.environ.get("DATABASE_URL")
    if not target and is_production() and not url:
        raise RuntimeError("DATABASE_URL is required in production.")
    if url:
        import psycopg

        conn, ddl, key = Conn(psycopg.connect(url), True), _PG, url
    else:
        path = target or os.environ.get("DB_PATH", "skillissue.db")
        conn, ddl, key = Conn(sqlite3.connect(path, timeout=30), False), _SQLITE, path
    try:
        with _schema_lock:
            if key not in _initialised:
                if conn.pg:
                    conn.execute("SELECT pg_advisory_xact_lock(734812901)")
                for stmt in ddl + _INDEXES:
                    conn.execute(stmt)
                conn.commit()
                _initialised.add(key)
    except Exception:
        conn.close()
        raise
    return conn


def insert(
    conn,
    *,
    ts,
    device,
    boss,
    heals,
    revives,
    charmless,
    bell,
    prosthetic,
    art,
    excluded=0,
    flag_reason=None
):
    conn.execute(
        """INSERT INTO submissions
           (ts,device,boss,heals,revives,charmless,bell,prosthetic,art,
            score,excluded,flag_reason)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ts,
            device,
            boss,
            heals,
            revives,
            int(charmless),
            int(bell),
            int(prosthetic),
            int(art),
            score_of(heals, revives),
            excluded,
            flag_reason,
        ),
    )
