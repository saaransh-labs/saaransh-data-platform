"""
How two status connect to the three stages:
  - Stage 1 → inserts rows into links with status = 'pending'       
  - Stage 2 → picks up links where status = 'pending', downloads,
  sets to done/failed, inserts into transcripts with status = 'pending'       
  - Stage 3 → picks up transcripts where status = 'pending', parses sets to done/failed
"""


import sqlite3
from pathlib import Path

class AlphastreetDB:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
    
    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS links (                    
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                url      TEXT UNIQUE NOT NULL,                    
                title    TEXT,
                date     TEXT,
                type     TEXT,                                    
                status   TEXT DEFAULT 'pending'   -- pending | done | failed
            );  
                                                                    
            CREATE TABLE IF NOT EXISTS transcripts (
                id       INTEGER PRIMARY KEY,                     
                link_id  INTEGER REFERENCES links(id),
                raw_path TEXT,
                status   TEXT DEFAULT 'pending'   -- pending | done | failed
            );
        """)
        self.conn.commit()

    def upsert_links(self, data: list[tuple]) -> None:
        self.conn.executemany("""
            INSERT INTO links (url, title, date, type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
        """, data)
        self.conn.commit()

    def link_exists(self, url: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM links WHERE url = ?", (url,)).fetchone()
        return row is not None
    
    def get_pending_links(self) -> list:
        return self.conn.execute(
            "SELECT * FROM links WHERE status = 'pending'"
        ).fetchall()
    
    def update_link_status(self, url: str, status: str) -> None:
        self.conn.execute(
            "UPDATE links SET status = ? WHERE link = ?", (url, status)
        )
        self.conn.commit()
    
    def close(self) -> None:
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self.close()