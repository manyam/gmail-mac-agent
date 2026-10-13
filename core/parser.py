import base64
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


@dataclass
class ParsedEmailMessage:
    message_id: str
    sender: str
    recipient: str
    date: str
    body_text: str


@dataclass
class ParsedEmailThread:
    thread_id: str
    subject: str
    participants: List[str]
    latest_date: str
    web_link: str
    messages: List[ParsedEmailMessage]
    history_id: str = ""

    def to_llm_text(self) -> str:
        """Converts thread into a clean conversational transcript for the LLM."""
        header = (
            f"=== THREAD: {self.subject} ===\n"
            f"ID: {self.thread_id}\n"
            f"Participants: {', '.join(self.participants)}\n"
            f"Date: {self.latest_date}\n"
            f"Link: {self.web_link}\n"
        )
        msg_texts = []
        for i, msg in enumerate(self.messages, start=1):
            msg_texts.append(
                f"[Message {i} from: {msg.sender} on {msg.date}]\n"
                f"{msg.body_text.strip()}\n"
            )
        return header + "\n" + "\n".join(msg_texts)


class EmailParser:
    """Parses raw Gmail API thread & message payloads into clean readable text."""

    @staticmethod
    def parse_thread(raw_thread: Dict[str, Any]) -> ParsedEmailThread:
        thread_id = raw_thread.get("id", "")
        raw_messages = raw_thread.get("messages", [])
        web_link = f"https://mail.google.com/mail/u/0/#all/{thread_id}"

        parsed_messages: List[ParsedEmailMessage] = []
        subject = "(No Subject)"
        participants: List[str] = []
        latest_date = ""

        for msg in raw_messages:
            parsed = EmailParser.parse_message(msg)
            if parsed:
                parsed_messages.append(parsed)
                if parsed.sender and parsed.sender not in participants:
                    participants.append(parsed.sender)
                latest_date = parsed.date

        if raw_messages:
            # Extract subject from first or last message
            for h in raw_messages[0].get("payload", {}).get("headers", []):
                if h.get("name", "").lower() == "subject":
                    subject = h.get("value", "(No Subject)")
                    break

        history_id = str(raw_thread.get("historyId", ""))

        return ParsedEmailThread(
            thread_id=thread_id,
            subject=subject,
            participants=participants,
            latest_date=latest_date,
            web_link=web_link,
            messages=parsed_messages,
            history_id=history_id,
        )

    @staticmethod
    def parse_message(raw_msg: Dict[str, Any]) -> Optional[ParsedEmailMessage]:
        message_id = raw_msg.get("id", "")
        payload = raw_msg.get("payload", {})
        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in payload.get("headers", [])
        }

        sender = headers.get("from", "Unknown Sender")
        recipient = headers.get("to", "")
        date = headers.get("date", "")

        raw_text, raw_html = EmailParser._extract_parts(payload)
        cleaned_body = EmailParser._clean_text(raw_text, raw_html)

        if not cleaned_body:
            # Fall back to snippet if body extraction was empty
            cleaned_body = raw_msg.get("snippet", "")

        # Truncate single message if abnormally long (e.g. system logs or automated reports)
        max_chars = 3500
        if len(cleaned_body) > max_chars:
            cleaned_body = cleaned_body[:max_chars] + "\n[...content truncated for brevity...]"

        return ParsedEmailMessage(
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            date=date,
            body_text=cleaned_body,
        )

    @staticmethod
    def _extract_parts(payload: Dict[str, Any]) -> tuple[str, str]:
        """Recursively extracts plain text and HTML payloads from MIME parts."""
        text_parts: List[str] = []
        html_parts: List[str] = []

        def recurse(part: Dict[str, Any]):
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            data_b64 = body.get("data")

            if data_b64:
                try:
                    # Gmail API uses URL-safe base64
                    decoded = base64.urlsafe_b64decode(data_b64.encode("ASCII")).decode(
                        "utf-8", errors="replace"
                    )
                    if mime_type == "text/plain":
                        text_parts.append(decoded)
                    elif mime_type == "text/html":
                        html_parts.append(decoded)
                except Exception:
                    pass

            for subpart in part.get("parts", []):
                recurse(subpart)

        recurse(payload)
        return "\n".join(text_parts), "\n".join(html_parts)

    @staticmethod
    def _clean_text(text: str, html: str) -> str:
        """Cleans and strips HTML, quotes, and whitespace."""
        content = text
        if not content.strip() and html.strip():
            if BeautifulSoup:
                try:
                    soup = BeautifulSoup(html, "html.parser")
                    for tag in soup(["script", "style", "noscript", "svg", "head", "meta"]):
                        tag.decompose()
                    content = soup.get_text(separator="\n")
                except Exception:
                    content = re.sub(r"<[^>]+>", " ", html)
            else:
                content = re.sub(r"<[^>]+>", " ", html)

        # Strip quoted email replies to reduce prompt size
        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            # Stop if historical quote header is reached
            if re.match(r"^On\s+.*,\s+.*wrote:$", stripped, re.IGNORECASE):
                break
            if stripped.startswith("-----Original Message-----"):
                break
            # Skip lines starting with quote symbol >
            if stripped.startswith(">"):
                continue
            lines.append(line)

        cleaned = "\n".join(lines)
        # Collapse multiple blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
