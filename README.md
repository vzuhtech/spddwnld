## Video Downloader Telegram Bot (yt-dlp)

A Telegram bot that fetches video info (title + thumbnail) from many sites via `yt-dlp` and provides inline buttons to download in available resolutions.

### Features
- Works with many video sites supported by `yt-dlp`
- Shows title and thumbnail preview
- Inline buttons for multiple resolutions (merging audio+video via ffmpeg if needed)

### Requirements
- Python 3.10+
- ffmpeg available in PATH (for merging video+audio when needed)
  - Windows: download from the official builds and add `ffmpeg\bin` to PATH.
- A Telegram Bot token from `@BotFather`

### Setup (Windows PowerShell)
1. Create a `.env` file in the `videodown` folder with:
   ```env
   BOT_TOKEN=123456789:YOUR_TELEGRAM_BOT_TOKEN
   ```
2. Create a virtual environment and install dependencies:
   ```powershell
   cd videodown
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```powershell
   python -m bot.main
   ```

### Usage
- Send your bot a message containing a video URL.
- The bot replies with a thumbnail, title, and buttons for available resolutions.
- Click a button to download; the bot uploads the resulting file (subject to Telegram bot size limits).

### Notes
- Large videos may exceed Telegram bot upload limits. Choose a lower resolution if upload fails or use the original site link.
- `yt-dlp` supports many platforms, but not all; some sites require cookies or login which are not handled by this bot.