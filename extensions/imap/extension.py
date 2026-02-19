"""
IMAP Email extension for MESH-API.

Monitors an email inbox via IMAP and forwards new messages onto the mesh:
- Polls an IMAP mailbox for unseen messages at a configurable interval.
- Optionally filters by subject line and/or sender address.
- Truncates the email body to fit mesh message limits.
- Marks processed emails as read (configurable).

This is an inbound-only extension.  Outbound email is handled by the
core SMTP functionality already built into mesh-api.
"""

import email
import email.header
import imaplib
import threading
import time

from extensions.base_extension import BaseExtension


class ImapExtension(BaseExtension):
    """IMAP inbox monitor → Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "IMAP"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def imap_server(self) -> str:
        return self.config.get("imap_server", "")

    @property
    def imap_port(self) -> int:
        return int(self.config.get("imap_port", 993))

    @property
    def imap_username(self) -> str:
        return self.config.get("imap_username", "")

    @property
    def imap_password(self) -> str:
        return self.config.get("imap_password", "")

    @property
    def use_ssl(self) -> bool:
        return bool(self.config.get("use_ssl", True))

    @property
    def mailbox(self) -> str:
        return self.config.get("mailbox", "INBOX")

    @property
    def subject_filter(self) -> str:
        return self.config.get("subject_filter", "")

    @property
    def sender_filter(self) -> str:
        return self.config.get("sender_filter", "")

    @property
    def mark_as_read(self) -> bool:
        return bool(self.config.get("mark_as_read", True))

    @property
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 60))

    @property
    def max_body_length(self) -> int:
        return int(self.config.get("max_body_length", 200))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()

        status = []
        if self.imap_server:
            status.append(f"server={self.imap_server}")
        if self.imap_username:
            status.append(f"user={self.imap_username}")
        if self.subject_filter:
            status.append(f"subj_filter={self.subject_filter}")

        self.log(f"IMAP enabled. {', '.join(status) if status else 'No settings configured.'}")

        if self.imap_server and self.imap_username and self.imap_password:
            self._poll_thread = threading.Thread(
                target=self._poll_imap,
                daemon=True,
                name="imap-poll",
            )
            self._poll_thread.start()
            self.log("IMAP polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("IMAP extension unloaded.")

    # ------------------------------------------------------------------
    # IMAP polling loop
    # ------------------------------------------------------------------

    def _poll_imap(self) -> None:
        time.sleep(5)

        while not self._stop_event.is_set():
            conn = None
            try:
                # Connect
                if self.use_ssl:
                    conn = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
                else:
                    conn = imaplib.IMAP4(self.imap_server, self.imap_port)

                conn.login(self.imap_username, self.imap_password)
                conn.select(self.mailbox)

                # Build search criteria
                criteria = ["UNSEEN"]
                if self.subject_filter:
                    criteria.append(f'SUBJECT "{self.subject_filter}"')
                if self.sender_filter:
                    criteria.append(f'FROM "{self.sender_filter}"')
                search_str = " ".join(criteria)

                status, data = conn.search(None, f"({search_str})")
                if status != "OK":
                    self.log("IMAP search failed.")
                    continue

                msg_ids = data[0].split()
                for msg_id in msg_ids:
                    try:
                        _, msg_data = conn.fetch(msg_id, "(RFC822)")
                        raw = msg_data[0][1]
                        msg = email.message_from_bytes(raw)

                        subject = self._decode_header(msg.get("Subject", ""))
                        sender = self._decode_header(msg.get("From", ""))
                        body = self._get_text_body(msg)

                        if body and len(body) > self.max_body_length:
                            body = body[:self.max_body_length] + "..."

                        formatted = f"[Email] From: {sender}\nSubj: {subject}\n{body or '(no body)'}"

                        log_fn = self.app_context.get("log_message")
                        if log_fn:
                            log_fn("IMAP", formatted, direct=False,
                                   channel_idx=self.inbound_channel_index)

                        if self.inbound_channel_index is not None:
                            self.send_to_mesh(formatted,
                                              channel_index=self.inbound_channel_index)

                        self.log(f"Forwarded email from {sender}: {subject}")

                        if self.mark_as_read:
                            conn.store(msg_id, "+FLAGS", "\\Seen")

                    except Exception as exc:
                        self.log(f"Error processing email {msg_id}: {exc}")

                conn.logout()
            except Exception as exc:
                self.log(f"IMAP poll error: {exc}")
                if conn:
                    try:
                        conn.logout()
                    except Exception:
                        pass
            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_header(value: str) -> str:
        """Decode RFC2047-encoded header values."""
        parts = email.header.decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    @staticmethod
    def _get_text_body(msg) -> str:
        """Extract the plain-text body from an email message."""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                cd = str(part.get("Content-Disposition", ""))
                if ct == "text/plain" and "attachment" not in cd:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace").strip()
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()
        return ""
