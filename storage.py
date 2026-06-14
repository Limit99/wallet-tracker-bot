"""SQLite storage untuk wallet yang di-track dan state transaksi terakhir."""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "wallets.db"


def init_db():
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id   INTEGER NOT NULL,
                chain     TEXT    NOT NULL,   -- 'evm:<chain>' atau 'solana'
                address   TEXT    NOT NULL,
                label     TEXT,
                last_seen TEXT,               -- penanda tx terakhir yang sudah dinotif (anti-dobel)
                added_at  INTEGER,            -- unix time saat wallet ditambahkan (gerbang waktu)
                UNIQUE(chat_id, chain, address)
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat ON wallets(chat_id)"
        )
        # --- migrasi DB lama: tambah kolom added_at kalau belum ada ---
        cols = [r["name"] for r in c.execute("PRAGMA table_info(wallets)").fetchall()]
        if "added_at" not in cols:
            c.execute("ALTER TABLE wallets ADD COLUMN added_at INTEGER")
            c.execute("UPDATE wallets SET added_at=? WHERE added_at IS NULL",
                      (int(time.time()),))


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_wallet(chat_id: int, chain: str, address: str, label: str | None) -> int | None:
    """Return id wallet baru, atau None kalau sudah ada."""
    try:
        with _conn() as c:
            cur = c.execute(
                "INSERT INTO wallets (chat_id, chain, address, label, added_at) "
                "VALUES (?,?,?,?,?)",
                (chat_id, chain, address, label, int(time.time())),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def remove_wallet(chat_id: int, address: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM wallets WHERE chat_id=? AND lower(address)=lower(?)",
            (chat_id, address),
        )
        return cur.rowcount


def list_wallets(chat_id: int):
    with _conn() as c:
        return c.execute(
            "SELECT * FROM wallets WHERE chat_id=? ORDER BY id", (chat_id,)
        ).fetchall()


def all_wallets():
    with _conn() as c:
        return c.execute("SELECT * FROM wallets").fetchall()


def set_last_seen(wallet_id: int, value: str):
    with _conn() as c:
        c.execute("UPDATE wallets SET last_seen=? WHERE id=?", (value, wallet_id))
