# 🎵 YouTube Music Downloader (Audio-Only)

A Streamlit application to **search**, **preview**, and **download MP3 audio** from YouTube.
Supports **direct URL input**, **cookie-based access for restricted videos**, and **batch downloading**.

## ✅ Features

### 🎧 Single Song Download
- Search YouTube by song name
- View top results (filtered under 10 minutes)
- Choose one and download as MP3
- Audio preview directly inside the app

### 🔗 Direct YouTube URL Support
Paste a full YouTube link and the app will:
- Detect it automatically
- Extract the real video title
- Bypass the search system
- Play & download the audio

### 🔐 Cookie-Based Restricted Video Access
Automatically handles:
- Age-restricted videos
- Login-required videos
- Geo-blocked content
- Private/limited videos (if user provides cookies)

Cookie system:
- Tries **no cookies** first (fastest)
- If restricted → uses **your saved cookies** from Streamlit Secrets
- If still restricted → allows user to **paste their own cookies**
- Uses Netscape format (standard for yt-dlp)

### 📦 Batch Download
Enter multiple song names separated by commas;
the app searches each, picks the first result, and downloads them.

## ✅ Installation (Local)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## ✅ Streamlit Secrets Format

Your app supports two optional secrets:

### `password`
Password to open the app:
```
password = "your_login_password"
```

### `youtube_cookies` (Optional)
Paste your YouTube cookies in **Netscape format**. Example (tabs are escaped here):

```
youtube_cookies = """
# Netscape HTTP Cookie File
.youtube.com\tTRUE\t/\tTRUE\t1700000000\tVISITOR_INFO1_LIVE\tAAAAAA12345
.youtube.com\tTRUE\t/\tTRUE\t1700000000\tYSC\tabcdEFGH12345
.youtube.com\tTRUE\t/\tTRUE\t1700000000\tLOGIN_INFO\t<your-login-info-token>
... 
"""
```

> The app only uses cookies **if necessary** (age-restricted, login-required, geo-restricted).
> If cookies fail, the user can paste new cookies inside the app.

## ✅ How to Export Cookies (Recommended)

Install the *Get Cookies.txt* browser extension and export the cookies in Netscape format, then paste into Streamlit Secrets.

## ✅ How It Works

The app uses **yt-dlp** with:
- Fine-tuned headers
- Cookie fallback
- Geo-proxy support (optional via secrets)
- Title extraction
- Fast audio-only streaming when possible

For restricted videos the app automatically attempts:
1. No cookies
2. Secret cookies
3. User-pasted cookies

## ✅ Disclaimer
This tool is for **personal use only**. Do not re-upload copyrighted content. Not affiliated with or endorsed by YouTube.
