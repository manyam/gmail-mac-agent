from datetime import datetime
from typing import List, Optional
from .parser import ParsedEmailThread


SYSTEM_INSTRUCTION = """You are an elite, privacy-preserving Personal Executive AI Assistant running locally on macOS.
Your mission is to read email threads and synthesize a clean, prioritized, and highly actionable Daily Brief.

Key Principles:
1. Executive Clarity: Be extremely concise, direct, and factual. Omit pleasantries, email signatures, and filler phrases.
2. Direct Actionability: If an email asks a question, requests a review, or has a deadline, clearly highlight the exact action required.
3. Link Integrity: ALWAYS include the provided markdown link `[Open Thread](https://mail.google.com/mail/u/0/#all/<THREAD_ID>)` for each item so the user can jump straight into Gmail.
4. Clean Categorization:
   - 🚨 Action Required & Urgent: Decisions, deadlines, unanswered questions requiring user reply.
   - 📌 Important Updates & FYIs: Confirmations, shipping, financial receipts, status milestones.
   - 📰 Highlights & Newsletters: Core 1-2 takeaway bullets from newsletters, digests, or announcements.
   - ⏳ Follow-Ups / Waiting On: Threads awaiting external or user follow-up.
"""


def build_daily_brief_prompt(
    threads: List[ParsedEmailThread], label: Optional[str] = None
) -> str:
    """Builds the complete prompt with sanitized email contents."""
    today_str = datetime.now().strftime("%A, %B %d, %Y")
    now_time_str = datetime.now().strftime("%I:%M %p")

    threads_text = "\n\n".join(t.to_llm_text() for t in threads)
    label_header = f" [{label}]" if label else ""
    label_context = f" for label '{label}'" if label else ""

    prompt = f"""Today is {today_str} ({now_time_str}).
Analyze the following {len(threads)} email threads{label_context} and generate the Daily Brief.

Follow this exact Markdown format:

# 📬 Daily Brief{label_header} — {today_str}
*Generated at {now_time_str} • {len(threads)} active threads analyzed*

---

## 🚨 Action Required & Urgent
(Items requiring a direct response, immediate decision, approval, or with approaching deadlines. If none, write "_No urgent action items today._")
- **[Sender Name]** Subject Line
  - **Action**: Specific action required
  - **Context**: 1-2 sentences on what this is about
  - 🔗 [Open Thread](https://mail.google.com/mail/u/0/#all/<thread_id>)

## 📌 Important Updates & FYIs
(Receipts, shipping, booking confirmations, project milestones, status changes. If none, write "_None today._")
- **[Sender Name]** Subject Line
  - Key takeaway or update details
  - 🔗 [Open Thread](https://mail.google.com/mail/u/0/#all/<thread_id>)

## 📰 Highlights & Newsletters
(Digests, community updates, or newsletters. Provide 1-2 high-value bullet takeaways. If none, write "_None today._")
- **[Publication/Sender]** Title
  - Core insight or key takeaway
  - 🔗 [Open Thread](https://mail.google.com/mail/u/0/#all/<thread_id>)

## ⏳ Follow-Ups & Pending
(Threads where a response is pending from someone else or awaiting future input. If none, write "_None today._")
- **[Sender Name]** Subject Line
  - Status of what is pending
  - 🔗 [Open Thread](https://mail.google.com/mail/u/0/#all/<thread_id>)

---
### 📊 Quick Stats
- Total Threads Analyzed: {len(threads)}
{f"- Label: {label}" if label else ""}

=== EMAIL THREAD DATA TO ANALYZE ===
{threads_text}
"""
    return prompt
