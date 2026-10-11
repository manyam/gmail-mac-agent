#!/usr/bin/env python3
"""
Gmail Daily Brief Agent for macOS
Local-first executive briefing agent using Ollama (Primary) & Gemini Flash (Backup).
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import load_config
from core.delivery import DeliveryManager
from core.llm_client import LLMClient


def check_gmail_dependencies():
    """Verify that Google API & parser dependencies are installed."""
    missing = []
    for mod, pkg in [
        ("googleapiclient", "google-api-python-client"),
        ("google_auth_oauthlib", "google-auth-oauthlib"),
        ("bs4", "beautifulsoup4"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    return missing


def run_auth_only(config):
    """Executes the one-time interactive OAuth browser login."""
    missing = check_gmail_dependencies()
    if missing:
        print(f"❌ Missing required dependencies: {', '.join(missing)}")
        print("Install them with:\n  pip install -r gmail_agent/requirements.txt\nor:\n  uv pip install -r gmail_agent/requirements.txt")
        sys.exit(1)

    from core.auth import GmailAuthManager

    print("=== Gmail OAuth Authentication Setup ===")
    auth_mgr = GmailAuthManager(
        credentials_path=config.gmail.credentials_path,
        token_path=config.gmail.token_path,
    )
    auth_mgr.get_credentials(interactive=True)
    print("Authentication verified successfully!")


def test_llm_connections(config):
    """Verifies Ollama connectivity and Gemini Flash backup."""
    print("=== Testing LLM Providers ===")
    llm = LLMClient(config.llm_primary, config.llm_backup)
    test_prompt = "Respond with one short sentence: 'Local Mac Agent LLM connection verified successfully.'"

    print(f"Testing Primary: Ollama ({config.llm_primary.model} at {config.llm_primary.base_url})...")
    try:
        ollama_resp = llm._call_ollama(test_prompt)
        print(f"✅ Ollama SUCCESS: {ollama_resp}\n")
    except Exception as e:
        print(f"❌ Ollama FAILED: {e}\n")

    print(f"Testing Backup: Gemini Flash ({config.llm_backup.model})...")
    try:
        gemini_resp = llm._call_gemini(test_prompt)
        print(f"✅ Gemini SUCCESS: {gemini_resp}\n")
    except Exception as e:
        print(f"❌ Gemini FAILED: {e}\n")


def run_pipeline(config, force: bool = False, dry_run: bool = False):
    """Executes the complete end-to-end daily brief generation pipeline."""
    missing = check_gmail_dependencies()
    if missing:
        print(f"❌ Missing required dependencies: {', '.join(missing)}")
        print("Install them with:\n  pip install -r gmail_agent/requirements.txt\nor:\n  uv pip install -r gmail_agent/requirements.txt")
        sys.exit(1)

    from core.auth import GmailAuthManager
    from core.gmail_client import GmailClient
    from core.prompts import build_daily_brief_prompt
    from core.state import StateManager

    print(f"=== Starting Gmail Daily Brief Run ===")
    print(f"Labels Filtered: {config.gmail.labels}")
    print(f"Output Directory: {config.output.daily_briefs_dir}")

    # 1. Initialize core components
    state_mgr = StateManager(config.gmail.state_db_path)
    auth_mgr = GmailAuthManager(
        credentials_path=config.gmail.credentials_path,
        token_path=config.gmail.token_path,
    )
    gmail_client = GmailClient(config.gmail, auth_mgr)
    delivery_mgr = DeliveryManager(
        output_dir=config.output.daily_briefs_dir,
        notification_enabled=config.output.notification.enabled,
        sound=config.output.notification.sound,
    )
    llm_client = LLMClient(config.llm_primary, config.llm_backup)

    # 2. Query and retrieve email threads
    parsed_threads = gmail_client.fetch_threads(state_manager=state_mgr, force=force)

    if not parsed_threads:
        msg = "No new unread or unprocessed email threads found for your filter criteria."
        print(f"[INFO] {msg}")
        delivery_mgr.notify_macos(msg, title="Gmail Agent: Up to Date")
        return

    print(f"[INFO] Successfully parsed {len(parsed_threads)} threads.")

    # 3. Dry run mode exit
    if dry_run:
        print("\n--- DRY RUN SUMMARY ---")
        for i, t in enumerate(parsed_threads, 1):
            print(f"{i}. [{t.latest_date}] {t.subject} (From: {', '.join(t.participants)})")
        print("\n[INFO] Dry run complete. No LLM calls made.")
        return

    # 4. Generate prompt & synthesize brief
    prompt = build_daily_brief_prompt(parsed_threads)
    print(f"[INFO] Synthesizing brief with LLM ({len(prompt)} prompt characters)...")

    brief_text, provider_meta = llm_client.generate(prompt)

    # 5. Save markdown brief to ~/Documents/GmailDailyBriefs/
    saved_path = delivery_mgr.save_brief(brief_text, provider_meta)

    # 6. Record processed threads in state DB
    for t in parsed_threads:
        state_mgr.mark_processed(
            thread_id=t.thread_id,
            history_id="digest",
            message_count=len(t.messages),
        )

    # 7. Send macOS notification banner
    notif_msg = f"{len(parsed_threads)} threads digested via {provider_meta}."
    delivery_mgr.notify_macos(notif_msg, title="☀️ Morning Brief Ready")

    print("\n" + "=" * 60)
    print(brief_text)
    print("=" * 60)
    print(f"\n[DONE] Brief written to: {saved_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Local Mac Gmail Daily Brief Agent (Ollama + Gemini Flash backup)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom config.yaml",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Run interactive Google OAuth authentication flow only",
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="Test connectivity to Ollama and Gemini Flash backup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query and parse emails without sending to LLM",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached threads in SQLite and re-process all matches",
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=None,
        help="Comma-separated labels to filter (e.g. 'INBOX,IMPORTANT')",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=None,
        help="Lookback window in hours (e.g. 24 or 48)",
    )

    args = parser.parse_args()

    config = load_config(args.config)

    # Apply CLI overrides
    if args.labels:
        config.gmail.labels = [lbl.strip() for lbl in args.labels.split(",") if lbl.strip()]
    if args.hours:
        config.gmail.lookback_hours = args.hours

    if args.auth:
        run_auth_only(config)
    elif args.test_llm:
        test_llm_connections(config)
    else:
        run_pipeline(config, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
