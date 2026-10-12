# 📬 Local Mac Gmail Daily Brief Agent

A privacy-first personal AI agent for macOS that reads your Gmail using specific label filters, aggregates conversation threads, and generates an actionable **Daily Brief** delivered directly to your Mac.

- **Primary Intelligence**: 100% On-Device & Private via **Ollama** (`gemma4:26b-mlx`). Zero email text leaves your laptop.
- **Automatic Fallback**: **Google Gemini Flash** (`gemini-3.8-flash`) via `$GOOGLE_API_KEY` if Ollama is paused or busy.
- **Delivery**: Formatted Markdown per label in `~/Documents/GmailDailyBriefs/<label>/` + native macOS notification banner.
- **Scheduling**: Native macOS `launchd` daemon (handles Mac sleep/wake seamlessly).
- **Security**: Strictly read-only OAuth scope (`gmail.readonly`), deduplicated in local SQLite cache.

---

## 🛠️ Quick Start

### 1. Install Dependencies

Navigate to the project root:
```bash
cd ~/src/gmail-agent
```

Using `uv` (recommended):
```bash
uv pip install -r requirements.txt
```
Or standard `pip`:
```bash
pip install -r requirements.txt
```

---

### 2. Google Cloud Setup (One-Time, ~3 min)

To allow the agent to read your personal Gmail:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (e.g. `Gmail-Mac-Agent`).
3. Under **APIs & Services** > **Library**, search for **Gmail API** and click **Enable**.
4. Under **APIs & Services** > **OAuth consent screen**:
   - Choose **External** and click **Create**.
   - Enter an app name (e.g., `Mac Gmail Agent`) and your email.
   - On the **Test users** page, click **Add Users** and add your own Gmail address (this allows you to authenticate without requiring Google app verification).
5. Under **APIs & Services** > **Credentials**:
   - Click **Create Credentials** > **OAuth client ID**.
   - Select Application type: **Desktop app**.
   - Click **Create**, then download the client secrets JSON.
6. Save the downloaded file to:
   ```bash
   mkdir -p ~/.gmail_agent
   mv ~/Downloads/client_secret_*.json ~/.gmail_agent/credentials.json
   ```

---

### 3. One-Time Authentication

Run the interactive authorization flow:
```bash
python3 main.py --auth
```
A browser tab will open. Sign in to your personal Gmail and grant read-only access. Your credentials will be saved locally to `~/.gmail_agent/token.json` with secure file permissions (`0600`).

---

### 4. Verify LLM Connections

Ensure your LLMs are configured:
```bash
# Optional: Set your backup Gemini API key
export GOOGLE_API_KEY="your-gemini-api-key"

# Verify both Ollama and Gemini fallback
python3 main.py --test-llm
```

If using Ollama, ensure your local model is pulled:
```bash
ollama pull gemma4:26b-mlx
```

---

### 5. Run the Daily Brief

Run the agent on demand:
```bash
python3 main.py
```

Useful CLI Flags:
```bash
# Preview matching emails without invoking LLMs
python3 main.py --dry-run

# Custom label filter (e.g. INBOX, Important, or custom labels)
python3 main.py --labels "INBOX,Important,Projects"

# Lookback window (e.g. 48 hours for Monday morning catch-up)
python3 main.py --hours 48

# Force re-processing of previously digested threads
python3 main.py --force
```

Generated briefs are stored in label subdirectories:
```bash
~/Documents/GmailDailyBriefs/<label>/Daily_Brief_YYYY-MM-DD.md
```

---

## ⏰ Set Up Background Scheduling (`launchd`)

Unlike cron, macOS `launchd` is specifically designed for MacBooks: if your Mac is asleep at 7:30 AM, `launchd` catches up and runs the job the moment you open your laptop.

To install the daily scheduler:
```bash
./launchd/install_daemon.sh
```

- **Schedule**: Every morning at **7:30 AM**.
- **Logs**: `~/.gmail_agent/logs/stdout.log` and `~/.gmail_agent/logs/stderr.log`.
- **Test the daemon immediately**:
  ```bash
  launchctl kickstart -k gui/$(id -u)/com.user.gmaildailybrief
  ```
- **To uninstall**:
  ```bash
  launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.user.gmaildailybrief.plist
  rm ~/Library/LaunchAgents/com.user.gmaildailybrief.plist
  ```

---

## ⚙️ Configuration (`config.yaml`)

You can edit `config.yaml` to customize:
- Labels to track (`INBOX`, `IMPORTANT`, custom labels).
- Exclusions (e.g., `-category:promotions -category:social`).
- Primary Ollama model and base URL.
- Backup Gemini model (`gemini-3.8-flash`).
- Notification sound (`Glass`, `Hero`, `Ping`, etc.).
