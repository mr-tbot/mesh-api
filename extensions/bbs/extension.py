"""
BBS (Bulletin Board System) extension for MESH-API.

Provides a full-featured store-and-forward bulletin board system
accessible over the Meshtastic mesh network.  Uses SQLite for
persistent storage.

Features:
- Multiple message boards with configurable defaults.
- Post, read, list, and search messages.
- Private messaging between mesh nodes.
- Message retention with automatic cleanup.
- New post announcements to the mesh.

Commands:
  /bbs help              — show all BBS commands
  /bbs boards            — list available boards
  /bbs read <board> [n]  — read last n messages from a board
  /bbs post <board> <msg>— post a message to a board
  /bbs search <term>     — search messages across all boards
  /bbs msg <node> <msg>  — send a private message
  /bbs inbox             — check private messages
  /bbs new <board_name>  — create a new board
  /bbs del <board> <id>  — delete a message (own messages only)
  /bbs info              — show BBS stats
"""

import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

from extensions.base_extension import BaseExtension


class BbsExtension(BaseExtension):
    """Mesh BBS with SQLite store-and-forward."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "BBS"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        cmds = {
            "/bbs": "Mesh BBS — /bbs help for commands",
        }
        return cmds

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def db_filename(self) -> str:
        return self.config.get("db_filename", "bbs.db")

    @property
    def board_name(self) -> str:
        return self.config.get("board_name", "MESH-BBS")

    @property
    def motd(self) -> str:
        return self.config.get("motd", "Welcome to the Mesh BBS!")

    @property
    def max_messages(self) -> int:
        return int(self.config.get("max_messages_per_board", 500))

    @property
    def max_message_length(self) -> int:
        return int(self.config.get("max_message_length", 500))

    @property
    def max_boards(self) -> int:
        return int(self.config.get("max_boards", 20))

    @property
    def default_boards(self) -> list:
        return self.config.get("default_boards",
                               ["general", "emergency", "trading", "tech"])

    @property
    def allow_private(self) -> bool:
        return bool(self.config.get("allow_private_messages", True))

    @property
    def retention_days(self) -> int:
        return int(self.config.get("message_retention_days", 90))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def announce_new(self) -> bool:
        return bool(self.config.get("announce_new_posts", True))

    @property
    def require_shortname(self) -> bool:
        return bool(self.config.get("require_shortname", True))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._db_path = os.path.join(self.extension_dir, self.db_filename)
        self._db_lock = threading.Lock()
        self._cleanup_thread = None
        self._stop_event = threading.Event()

        self._init_db()
        self.log(f"BBS '{self.board_name}' loaded. DB: {self._db_path}")

        # Start periodic cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="bbs-cleanup",
        )
        self._cleanup_thread.start()

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        self.log("BBS extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command != "/bbs":
            return None

        parts = args.strip().split(None, 1) if args.strip() else []
        subcmd = parts[0].lower() if parts else "help"
        subargs = parts[1] if len(parts) > 1 else ""

        sender_id = node_info.get("node_id", "unknown")
        shortname = node_info.get("shortname", "?")

        if subcmd == "help":
            return self._help()
        elif subcmd == "boards":
            return self._list_boards()
        elif subcmd == "read":
            return self._read_board(subargs)
        elif subcmd == "post":
            return self._post_message(subargs, sender_id, shortname)
        elif subcmd == "search":
            return self._search(subargs)
        elif subcmd == "msg":
            return self._send_private(subargs, sender_id, shortname)
        elif subcmd == "inbox":
            return self._check_inbox(sender_id)
        elif subcmd == "new":
            return self._create_board(subargs, sender_id)
        elif subcmd == "del":
            return self._delete_message(subargs, sender_id)
        elif subcmd == "info":
            return self._board_info()
        elif subcmd == "motd":
            return self.motd
        else:
            return f"Unknown BBS command: {subcmd}. Try /bbs help"

    # ------------------------------------------------------------------
    # Database initialisation
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS boards (
                        name TEXT PRIMARY KEY,
                        created_by TEXT,
                        created_at TEXT
                    )
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        board TEXT NOT NULL,
                        sender_id TEXT NOT NULL,
                        sender_name TEXT NOT NULL,
                        body TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (board) REFERENCES boards(name)
                    )
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS private_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        from_id TEXT NOT NULL,
                        from_name TEXT NOT NULL,
                        to_id TEXT NOT NULL,
                        body TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        read INTEGER DEFAULT 0
                    )
                """)
                # Create default boards
                now = datetime.now(timezone.utc).isoformat()
                for board in self.default_boards:
                    c.execute(
                        "INSERT OR IGNORE INTO boards (name, created_by, created_at) "
                        "VALUES (?, ?, ?)",
                        (board.lower(), "system", now),
                    )
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # BBS subcommands
    # ------------------------------------------------------------------

    def _help(self) -> str:
        lines = [
            f"📋 {self.board_name} — Commands:",
            "/bbs boards        — list boards",
            "/bbs read <board> [n] — read messages",
            "/bbs post <board> <msg> — post message",
            "/bbs search <text> — search all boards",
        ]
        if self.allow_private:
            lines.append("/bbs msg <node_id> <msg> — private msg")
            lines.append("/bbs inbox — check private msgs")
        lines.extend([
            "/bbs new <name>    — create board",
            "/bbs del <board> <id> — delete own msg",
            "/bbs info          — BBS statistics",
        ])
        return "\n".join(lines)

    def _list_boards(self) -> str:
        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT name FROM boards ORDER BY name")
                boards = [row[0] for row in c.fetchall()]
                # Get message counts
                counts = {}
                for b in boards:
                    c.execute("SELECT COUNT(*) FROM messages WHERE board=?", (b,))
                    counts[b] = c.fetchone()[0]
            finally:
                conn.close()

        if not boards:
            return "No boards. Create one with /bbs new <name>"
        lines = ["📋 Boards:"]
        for b in boards:
            lines.append(f"  #{b} ({counts.get(b, 0)} msgs)")
        return "\n".join(lines)

    def _read_board(self, args: str) -> str:
        parts = args.strip().split()
        if not parts:
            return "Usage: /bbs read <board> [count]"
        board = parts[0].lower().lstrip("#")
        count = 5
        if len(parts) > 1:
            try:
                count = min(int(parts[1]), 20)
            except ValueError:
                count = 5

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT name FROM boards WHERE name=?", (board,))
                if not c.fetchone():
                    return f"Board '{board}' not found. /bbs boards to list."
                c.execute(
                    "SELECT id, sender_name, body, timestamp FROM messages "
                    "WHERE board=? ORDER BY id DESC LIMIT ?",
                    (board, count),
                )
                msgs = c.fetchall()
            finally:
                conn.close()

        if not msgs:
            return f"No messages in #{board}."
        lines = [f"📋 #{board} (last {len(msgs)}):"]
        for msg_id, sender, body, ts in reversed(msgs):
            # Shorten timestamp
            short_ts = ts[5:16] if len(ts) > 16 else ts
            lines.append(f"  [{msg_id}] {sender} ({short_ts}): {body}")
        return "\n".join(lines)

    def _post_message(self, args: str, sender_id: str, sender_name: str) -> str:
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: /bbs post <board> <message>"
        board = parts[0].lower().lstrip("#")
        body = parts[1]

        if len(body) > self.max_message_length:
            return f"Message too long (max {self.max_message_length} chars)."

        now = datetime.now(timezone.utc).isoformat()

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT name FROM boards WHERE name=?", (board,))
                if not c.fetchone():
                    return f"Board '{board}' not found."
                # Check message limit
                c.execute("SELECT COUNT(*) FROM messages WHERE board=?", (board,))
                count = c.fetchone()[0]
                if count >= self.max_messages:
                    # Delete oldest
                    c.execute(
                        "DELETE FROM messages WHERE id IN "
                        "(SELECT id FROM messages WHERE board=? ORDER BY id ASC LIMIT 1)",
                        (board,),
                    )
                c.execute(
                    "INSERT INTO messages (board, sender_id, sender_name, body, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (board, sender_id, sender_name, body, now),
                )
                msg_id = c.lastrowid
                conn.commit()
            finally:
                conn.close()

        # Announce new post
        if self.announce_new:
            announce = f"📝 New post in #{board} by {sender_name}: {body[:80]}"
            self.send_to_mesh(announce, channel_index=self.broadcast_channel)

        return f"✅ Posted to #{board} (msg #{msg_id})."

    def _search(self, query: str) -> str:
        if not query.strip():
            return "Usage: /bbs search <text>"
        term = f"%{query.strip()}%"

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute(
                    "SELECT id, board, sender_name, body FROM messages "
                    "WHERE body LIKE ? ORDER BY id DESC LIMIT 10",
                    (term,),
                )
                results = c.fetchall()
            finally:
                conn.close()

        if not results:
            return f"No messages matching '{query.strip()}'."
        lines = [f"🔍 Search: '{query.strip()}' ({len(results)} results):"]
        for msg_id, board, sender, body in results:
            short = body[:60] + "..." if len(body) > 60 else body
            lines.append(f"  [{msg_id}] #{board} {sender}: {short}")
        return "\n".join(lines)

    def _send_private(self, args: str, from_id: str, from_name: str) -> str:
        if not self.allow_private:
            return "Private messaging is disabled."
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: /bbs msg <node_id> <message>"
        to_id = parts[0]
        body = parts[1]

        if len(body) > self.max_message_length:
            return f"Message too long (max {self.max_message_length} chars)."

        now = datetime.now(timezone.utc).isoformat()

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO private_messages "
                    "(from_id, from_name, to_id, body, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (from_id, from_name, to_id, body, now),
                )
                conn.commit()
            finally:
                conn.close()

        return f"✉️ Private message sent to {to_id}."

    def _check_inbox(self, node_id: str) -> str:
        if not self.allow_private:
            return "Private messaging is disabled."

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute(
                    "SELECT id, from_name, body, timestamp FROM private_messages "
                    "WHERE to_id=? AND read=0 ORDER BY id ASC LIMIT 10",
                    (node_id,),
                )
                msgs = c.fetchall()
                # Mark as read
                if msgs:
                    ids = [str(m[0]) for m in msgs]
                    c.execute(
                        f"UPDATE private_messages SET read=1 "
                        f"WHERE id IN ({','.join('?' * len(ids))})",
                        ids,
                    )
                    conn.commit()
            finally:
                conn.close()

        if not msgs:
            return "📭 No new private messages."
        lines = [f"📬 {len(msgs)} new message(s):"]
        for _, from_name, body, ts in msgs:
            short_ts = ts[5:16] if len(ts) > 16 else ts
            lines.append(f"  From {from_name} ({short_ts}): {body}")
        return "\n".join(lines)

    def _create_board(self, args: str, sender_id: str) -> str:
        board = args.strip().lower()
        if not board:
            return "Usage: /bbs new <board_name>"
        if not board.isalnum() and not all(c.isalnum() or c in "-_" for c in board):
            return "Board names must be alphanumeric (hyphens/underscores ok)."
        if len(board) > 20:
            return "Board name too long (max 20 chars)."

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM boards")
                count = c.fetchone()[0]
                if count >= self.max_boards:
                    return f"Maximum boards ({self.max_boards}) reached."
                c.execute("SELECT name FROM boards WHERE name=?", (board,))
                if c.fetchone():
                    return f"Board '{board}' already exists."
                now = datetime.now(timezone.utc).isoformat()
                c.execute(
                    "INSERT INTO boards (name, created_by, created_at) VALUES (?, ?, ?)",
                    (board, sender_id, now),
                )
                conn.commit()
            finally:
                conn.close()

        return f"✅ Board #{board} created."

    def _delete_message(self, args: str, sender_id: str) -> str:
        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /bbs del <board> <message_id>"
        board = parts[0].lower().lstrip("#")
        try:
            msg_id = int(parts[1])
        except ValueError:
            return "Message ID must be a number."

        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute(
                    "SELECT sender_id FROM messages WHERE id=? AND board=?",
                    (msg_id, board),
                )
                row = c.fetchone()
                if not row:
                    return f"Message #{msg_id} not found in #{board}."
                if row[0] != sender_id:
                    return "You can only delete your own messages."
                c.execute("DELETE FROM messages WHERE id=?", (msg_id,))
                conn.commit()
            finally:
                conn.close()

        return f"🗑️ Message #{msg_id} deleted from #{board}."

    def _board_info(self) -> str:
        with self._db_lock:
            conn = sqlite3.connect(self._db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM boards")
                boards = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM messages")
                messages = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM private_messages")
                pms = c.fetchone()[0]
                c.execute(
                    "SELECT COUNT(DISTINCT sender_id) FROM messages"
                )
                users = c.fetchone()[0]
            finally:
                conn.close()

        return (
            f"📊 {self.board_name} Stats:\n"
            f"Boards: {boards}\n"
            f"Messages: {messages}\n"
            f"Private Messages: {pms}\n"
            f"Unique Posters: {users}\n"
            f"Retention: {self.retention_days} days"
        )

    # ------------------------------------------------------------------
    # Periodic cleanup
    # ------------------------------------------------------------------

    def _cleanup_loop(self) -> None:
        """Periodically remove old messages past retention period."""
        time.sleep(60)  # Wait before first cleanup
        while not self._stop_event.is_set():
            try:
                cutoff = (
                    datetime.now(timezone.utc) - timedelta(days=self.retention_days)
                ).isoformat()
                with self._db_lock:
                    conn = sqlite3.connect(self._db_path)
                    try:
                        c = conn.cursor()
                        c.execute(
                            "DELETE FROM messages WHERE timestamp < ?",
                            (cutoff,),
                        )
                        deleted_msgs = c.rowcount
                        c.execute(
                            "DELETE FROM private_messages WHERE timestamp < ?",
                            (cutoff,),
                        )
                        deleted_pms = c.rowcount
                        conn.commit()
                    finally:
                        conn.close()
                if deleted_msgs or deleted_pms:
                    self.log(f"Cleanup: removed {deleted_msgs} msgs, {deleted_pms} PMs "
                             f"older than {self.retention_days} days.")
            except Exception as exc:
                self.log(f"BBS cleanup error: {exc}")

            # Run cleanup every 6 hours
            for _ in range(21600):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
