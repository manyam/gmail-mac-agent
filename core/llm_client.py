import json
import os
import urllib.error
import urllib.request
from typing import Optional, Tuple

from .config import LLMConfig
from .prompts import SYSTEM_INSTRUCTION


class LLMClient:
    """
    Manages dual-engine LLM inference:
    Primary: Local Ollama (private, 100% on-device)
    Backup: Google Gemini Flash (uses GOOGLE_API_KEY from environment)
    """

    def __init__(self, primary_config: LLMConfig, backup_config: LLMConfig):
        self.primary = primary_config
        self.backup = backup_config

    def generate(self, user_prompt: str) -> Tuple[str, str]:
        """
        Attempts generation with primary (Ollama).
        If Ollama fails or times out, seamlessly falls back to Gemini Flash.
        Returns (brief_text, provider_info_string).
        """
        # 1. Attempt Primary: Ollama
        try:
            print(f"[INFO] Invoking Primary LLM: Ollama ({self.primary.model})...")
            text = self._call_ollama(user_prompt)
            provider_str = f"Local Ollama (`{self.primary.model}`)"
            return text, provider_str
        except Exception as e:
            print(
                f"[WARN] Primary LLM (Ollama) failed: {e}\n"
                f"[INFO] Automatically falling back to backup: Gemini Flash ({self.backup.model})..."
            )

        # 2. Attempt Backup: Gemini Flash
        try:
            text = self._call_gemini(user_prompt)
            provider_str = f"Gemini Flash (`{self.backup.model}` [Fallback])"
            return text, provider_str
        except Exception as e:
            raise RuntimeError(
                f"Both Primary (Ollama) and Backup (Gemini) failed.\n"
                f"Gemini error: {e}\n"
                "Please verify that either Ollama is running (`ollama serve`) or "
                f"export {self.backup.api_key_env}='<your_gemini_api_key>'."
            )

    def _call_ollama(self, prompt: str) -> str:
        """Invokes Ollama API via local HTTP request."""
        url = f"{self.primary.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.primary.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.primary.timeout_seconds) as response:
            if response.status != 200:
                raise RuntimeError(f"Ollama returned HTTP status {response.status}")
            data = json.loads(response.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip()

    def _call_gemini(self, prompt: str) -> str:
        """Invokes Gemini Flash API via official REST endpoint using GOOGLE_API_KEY."""
        api_key_var = self.backup.api_key_env or "GOOGLE_API_KEY"
        api_key = os.environ.get(api_key_var)

        if not api_key:
            raise ValueError(
                f"Environment variable '{api_key_var}' is not set. "
                "Set it with: export GOOGLE_API_KEY='your_api_key_here'"
            )

        model_name = self.backup.model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={api_key}"
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}],
            },
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.backup.timeout_seconds) as response:
                if response.status != 200:
                    raise RuntimeError(f"Gemini API returned HTTP {response.status}")
                data = json.loads(response.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError(f"No candidates returned from Gemini: {data}")
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise RuntimeError("Empty content part from Gemini candidate")
                return parts[0].get("text", "").strip()
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API HTTP Error {he.code}: {err_body}")
