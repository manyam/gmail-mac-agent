import math
from typing import Any, Dict, List, Optional
from googleapiclient.discovery import build

from .auth import GmailAuthManager
from .config import GmailConfig
from .parser import EmailParser, ParsedEmailThread
from .state import StateManager


class GmailClient:
    """Encapsulates querying and fetching email threads via Gmail REST API."""

    def __init__(self, config: GmailConfig, auth_manager: GmailAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self._service = None

    @property
    def service(self):
        if not self._service:
            creds = self.auth_manager.get_credentials(interactive=True)
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def build_query(self, labels: List[str], additional_query: str, lookback_hours: int) -> str:
        """Constructs an optimized Gmail search query."""
        query_parts = []

        # 1. Label constraints
        if labels:
            formatted_labels = []
            for lbl in labels:
                lbl_clean = lbl.strip()
                if not lbl_clean:
                    continue
                if " " in lbl_clean and not (lbl_clean.startswith('"') and lbl_clean.endswith('"')):
                    formatted_labels.append(f'label:"{lbl_clean}"')
                else:
                    formatted_labels.append(f"label:{lbl_clean}")

            if len(formatted_labels) == 1:
                query_parts.append(formatted_labels[0])
            elif len(formatted_labels) > 1:
                label_clause = " OR ".join(formatted_labels)
                query_parts.append(f"({label_clause})")

        # 2. Time constraint (Gmail supports newer_than:1d / 2d etc.)
        days = max(1, math.ceil(lookback_hours / 24))
        query_parts.append(f"newer_than:{days}d")

        # 3. Additional query exclusions (e.g. promotions, spam)
        if additional_query.strip():
            query_parts.append(additional_query.strip())

        return " ".join(query_parts)

    def fetch_threads(
        self, state_manager: StateManager, force: bool = False, label: Optional[str] = None
    ) -> List[ParsedEmailThread]:
        """Queries and parses recent email threads, skipping previously processed ones."""
        target_labels = [label] if label else self.config.labels
        query = self.build_query(
            target_labels,
            self.config.additional_query,
            self.config.lookback_hours,
        )
        print(f"[INFO] Querying Gmail with: '{query}'")

        response = (
            self.service.users()
            .threads()
            .list(userId="me", q=query, maxResults=self.config.max_threads)
            .execute()
        )

        raw_threads_meta = response.get("threads", [])
        print(f"[INFO] Found {len(raw_threads_meta)} matching threads in Gmail.")

        if not raw_threads_meta:
            return []

        # Filter out already digested threads
        threads_to_process = state_manager.filter_unseen_threads(
            raw_threads_meta, force=force, label=label
        )
        print(f"[INFO] Threads to process after deduplication: {len(threads_to_process)}")

        parsed_threads: List[ParsedEmailThread] = []
        for t_meta in threads_to_process:
            t_id = t_meta.get("id")
            try:
                full_thread = (
                    self.service.users()
                    .threads()
                    .get(userId="me", id=t_id, format="full")
                    .execute()
                )
                parsed = EmailParser.parse_thread(full_thread)
                if parsed and parsed.messages:
                    parsed_threads.append(parsed)
            except Exception as e:
                print(f"[WARN] Failed to fetch thread {t_id}: {e}")

        return parsed_threads
