"""
db_manager.py - SQLite Database Manager for Outreach Run History
Handles all CRUD operations for run logs, message logs, and config.
"""

import sqlite3
import os
import datetime
import pytz

DB_PATH = os.path.abspath("./outreach_logs.db")
PKT = pytz.timezone('Asia/Karachi')

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize DB tables on first run."""
    conn = get_connection()
    cur = conn.cursor()

    # Table 1: run_sessions - one row per full bot run
    cur.execute("""
        CREATE TABLE IF NOT EXISTS run_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,           -- 'facebook' or 'instagram'
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT DEFAULT 'running',    -- 'running', 'done', 'error'
            new_messages_sent INTEGER DEFAULT 0,
            followups_sent INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            row_start INTEGER DEFAULT 2,
            row_end INTEGER DEFAULT 0,
            daily_limit INTEGER DEFAULT 10,
            triggered_by TEXT DEFAULT 'scheduler'  -- 'scheduler' or 'manual'
        )
    """)

    # Table 2: message_logs - one row per message sent
    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            platform TEXT,
            name TEXT,
            profile_url TEXT,
            message_type TEXT,    -- 'new_outreach', '1st_followup', '2nd_followup'
            status TEXT,          -- 'sent', 'skipped', 'error', 'replied'
            reason TEXT,          -- reason for skip/error
            sent_at TEXT,
            FOREIGN KEY (session_id) REFERENCES run_sessions(id)
        )
    """)

    # Table 3: run_log_lines - raw terminal-style log lines per session
    cur.execute("""
        CREATE TABLE IF NOT EXISTS run_log_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            logged_at TEXT,
            line TEXT,
            FOREIGN KEY (session_id) REFERENCES run_sessions(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")

# ---- Run Session CRUD ----

def create_session(platform, row_start, row_end, daily_limit, triggered_by="scheduler"):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now(PKT).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO run_sessions (platform, started_at, status, row_start, row_end, daily_limit, triggered_by)
        VALUES (?, ?, 'running', ?, ?, ?, ?)
    """, (platform, now, row_start, row_end, daily_limit, triggered_by))
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id

def finish_session(session_id, new_sent, followups_sent, skipped, status="done"):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now(PKT).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        UPDATE run_sessions
        SET finished_at=?, status=?, new_messages_sent=?, followups_sent=?, skipped=?
        WHERE id=?
    """, (now, status, new_sent, followups_sent, skipped, session_id))
    conn.commit()
    conn.close()

def get_all_sessions(limit=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM run_sessions ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_session_by_id(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM run_sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM run_log_lines WHERE session_id=?", (session_id,))
    cur.execute("DELETE FROM message_logs WHERE session_id=?", (session_id,))
    cur.execute("DELETE FROM run_sessions WHERE id=?", (session_id,))
    conn.commit()
    conn.close()

# ---- Message Logs CRUD ----

def log_message(session_id, platform, name, profile_url, message_type, status, reason=""):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now(PKT).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO message_logs (session_id, platform, name, profile_url, message_type, status, reason, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, platform, name, profile_url, message_type, status, reason, now))
    conn.commit()
    conn.close()

def get_session_messages(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM message_logs WHERE session_id=? ORDER BY id ASC", (session_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ---- Log Lines ----

def add_log_line(session_id, line):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now(PKT).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO run_log_lines (session_id, logged_at, line) VALUES (?, ?, ?)
    """, (session_id, now, line))
    conn.commit()
    conn.close()

def get_log_lines(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT logged_at, line FROM run_log_lines WHERE session_id=? ORDER BY id ASC", (session_id,))
    rows = cur.fetchall()
    conn.close()
    return [f"[{r['logged_at']}] {r['line']}" for r in rows]

# Initialize on import
init_db()
