import streamlit as st
from streamlit_javascript import st_javascript
import json
import yt_dlp
import base64
import tempfile
import os
import re

st.set_page_config(page_title="Music Downloader", page_icon="🎵")

# -------------------- Password Auth --------------------
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# -------------------- Local Storage Helpers --------------------
def get_from_local_storage(k):
    v = st_javascript(f"JSON.parse(localStorage.getItem('{k}'));")
    return v or {}

def set_to_local_storage(k, v):
    jdata = json.dumps(v)
    st_javascript(f"localStorage.setItem('{k}', JSON.stringify({jdata}));")

# -------------------- Helpers --------------------
def get_binary_file_downloader_html(bin_file, song_title):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', song_title)[:120]
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{safe_title}.mp3">Download {safe_title}</a>'
    return href

def _write_cookies_to_file(cookie_text):
    """Write Netscape-format cookie text to a temporary file and return path."""
    if not cookie_text or not cookie_text.strip():
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    tmp.write(cookie_text.encode("utf-8"))
    tmp.flush()
    tmp.close()
    return tmp.name

def _remove_temp_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def searchYouTube(query):
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch10',
        'skip_download': True,
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            for entry in info.get('entries', []):
                title = entry.get('title')
                duration = entry.get('duration')
                video_id = entry.get('id')
                if not duration or duration > 600:
                    continue
                minutes = duration // 60
                seconds = duration % 60
                dur_str = f"{minutes}:{seconds:02d}"
                results.append((title, dur_str, f"https://www.youtube.com/watch?v={video_id}"))
        return results
    except Exception as e:
        st.error(f"Search failed: {e}")
        return []

# -------------------- URL detection --------------------
def is_youtube_url(text):
    if not text:
        return False
    text = text.strip()
    return ("youtube.com/watch" in text) or ("youtu.be/" in text)

def extract_title_from_url(url):
    try:
        ydl_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title') or "Direct Audio"
            return title
    except Exception:
        return "Direct Audio"

# -------------------- Robust downloader with secret-cookie fallback + paste override --------------------
def downloadYTFromLink(link, song_title):
    """
    Behaviour:
    1) Try streaming (no cookies) -> fast
    2) If restricted (403 / login required / age restriction), try with secret cookies (if present)
       and show an info message: "This video requires sign-in. Using stored cookies from app secrets to try access."
    3) If still blocked, show an expander to paste cookies and retry using pasted cookies.
    4) If pasted cookies used, show info: "User-supplied cookies are being used for this download."
    """

    # browser-like headers
    http_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.youtube.com/",
    }

    # helper to attempt streaming (extract_info -> get direct audio url)
    def try_stream(cookiefile=None, proxy=None):
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "http_headers": http_headers,
        }
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile
        if proxy:
            ydl_opts["geo_verification_proxy"] = proxy
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            audio_url = info.get("url")
            if not audio_url:
                for f in info.get("formats", []):
                    if f.get("acodec") != "none" and f.get("url"):
                        audio_url = f.get("url")
                        break
            return audio_url, info

    # helper to do full download to mp3
    def try_download(cookiefile=None, proxy=None):
        ydl_download_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "outtmpl": "song",
            "nocheckcertificate": True,
            "http_headers": http_headers,
        }
        if cookiefile:
            ydl_download_opts["cookiefile"] = cookiefile
        if proxy:
            ydl_download_opts["geo_verification_proxy"] = proxy
        with yt_dlp.YoutubeDL(ydl_download_opts) as ydl:
            ydl.cache.remove()
            ydl.download([link])

    # Step 1: Try fast streaming without cookies
    try:
        audio_url, info = try_stream(cookiefile=None, proxy=st.secrets.get("geo_verification_proxy", None))
        if audio_url:
            st.caption("Playing audio (no cookies required).")
            st.audio(audio_url)
            return
    except Exception as e:
        err_msg = str(e).lower()

    # detect likely restriction keywords from exception or info (if available)
    def _is_restriction_error(msg_or_info):
        s = ""
        if isinstance(msg_or_info, str):
            s = msg_or_info.lower()
        else:
            s = str(msg_or_info).lower()
        keys = ["403", "forbidden", "sign in", "sign-in", "login required", "age-restricted", "age restricted", "not available", "private video", "protected content", "needs login", "account required"]
        return any(k in s for k in keys)

    # Step 2: Try with secret cookies (if present)
    secret_cookie_text = st.secrets.get("youtube_cookies", "").strip()
    secret_cookie_file = None
    tried_with_secret = False
    if secret_cookie_text:
        # indicate to user in an info box (you chose option A: st.info)
        st.info("This video requires sign-in or is restricted. Using stored cookies from app secrets to try access.")
        secret_cookie_file = _write_cookies_to_file(secret_cookie_text)
        tried_with_secret = True
        try:
            audio_url, info = try_stream(cookiefile=secret_cookie_file, proxy=st.secrets.get("geo_verification_proxy", None))
            if audio_url:
                st.caption("Playing audio using stored cookies.")
                st.audio(audio_url)
                _remove_temp_file(secret_cookie_file)
                return
        except Exception as e:
            err_msg = str(e).lower()

    # Step 3: Attempt full download with secret cookies (if tried)
    if tried_with_secret:
        try:
            try_download(cookiefile=secret_cookie_file, proxy=st.secrets.get("geo_verification_proxy", None))
            st.audio("song.mp3")
            st.markdown(get_binary_file_downloader_html("song.mp3", song_title), unsafe_allow_html=True)
            _remove_temp_file(secret_cookie_file)
            return
        except Exception as e:
            err_msg = str(e).lower()
            _remove_temp_file(secret_cookie_file)

    # Step 4: If still failing, show optional paste-expander for user-supplied cookies
    show_exp = st.expander("Optional: Paste your own YouTube cookies (Netscape format) to access age-restricted / sign-in videos")
    with show_exp:
        pasted = st.text_area("Paste cookies.txt content here (Netscape format). Leave empty to skip.", height=200, key=f"paste_{song_title}")
        use_pasted = st.button("Use pasted cookies for this attempt", key=f"use_{song_title}")
        if use_pasted and pasted.strip():
            user_cookie_file = _write_cookies_to_file(pasted.strip())
            st.info("User-supplied cookies are being used for this download.")
            try:
                # first try streaming
                audio_url, info = try_stream(cookiefile=user_cookie_file, proxy=st.secrets.get("geo_verification_proxy", None))
                if audio_url:
                    st.caption("Playing audio using user-supplied cookies.")
                    st.audio(audio_url)
                    _remove_temp_file(user_cookie_file)
                    return
            except Exception:
                pass
            try:
                try_download(cookiefile=user_cookie_file, proxy=st.secrets.get("geo_verification_proxy", None))
                st.audio("song.mp3")
                st.markdown(get_binary_file_downloader_html("song.mp3", song_title), unsafe_allow_html=True)
                _remove_temp_file(user_cookie_file)
                return
            except Exception as e:
                st.error(f"Download failed even with user cookies: {e}")
                _remove_temp_file(user_cookie_file)
                return

    # If we reach here, we couldn't get it
    st.error("Unable to retrieve this video/audio. It may be geo-restricted, age-restricted, or require a logged-in account. Try pasting cookies above or running locally with your account cookies.")

# -------------------- Streamlit UI --------------------
if get_from_local_storage("password_correct"):
    authenticated = True
else:
    authenticated = check_password()

if authenticated:
    set_to_local_storage("password_correct", True)

    st.title("🎶 YouTube Music Downloader")
    st.write("Download or listen to music directly from YouTube in audio format (MP3).")
    st.warning("⚠️ This app is for personal use only and not affiliated with YouTube.")

    # Tabs
    tab1, tab2 = st.tabs(["🎧 Download Song", "📦 Batch Download"])

    def is_checkbox_filled():
        return 'songSelection' in st.session_state and st.session_state['songSelection']

    with tab1:
        st.subheader("Download a specific song")

        with st.form("search_form"):
            search = st.text_input("Search for a song or paste a YouTube URL:")
            submit_button = st.form_submit_button("Get Relevant Songs")

        if submit_button or is_checkbox_filled():
            # If input is a YouTube URL -> Option A behaviour (direct download)
            if is_youtube_url(search):
                st.info("Detected YouTube URL — retrieving audio...")
                title = extract_title_from_url(search)
                downloadYTFromLink(search, title)
            else:
                # Add-on: Refresh when new input given
                if "last_query" in st.session_state and st.session_state["last_query"] != search:
                    for key in ["options", "options_titles", "songSelection"]:
                        st.session_state.pop(key, None)
                st.session_state["last_query"] = search

                if not is_checkbox_filled():
                    st.info("Retrieving search results...")
                    options = searchYouTube(search)
                    if not options:
                        st.warning("No valid results found.")
                        st.stop()

                    options.insert(0, ("Select a song (disabled)", None, None))
                    options = [(idx, opt[0], opt[1], opt[2]) for idx, opt in enumerate(options)]

                    options_titles = ["Select a song (disabled)"]
                    options_titles.extend([f"{idx+1}. {opt[0]} — {opt[1]}" for idx, opt in enumerate(options[1:])])

                    st.session_state['options_titles'] = options_titles
                    st.session_state['options'] = options
                else:
                    options_titles = st.session_state['options_titles']
                    options = st.session_state['options']

                choice = st.selectbox("Choose a song", options, format_func=lambda x: options_titles[x[0]])
                st.session_state['songSelection'] = choice

                if choice[0] != 0 and is_checkbox_filled():
                    st.success(f"Downloading: {options[choice[0]][1]}")
                    downloadYTFromLink(options[choice[0]][3], options[choice[0]][1])

    with tab2:
        st.subheader("Batch Download (downloads first result per song)")
        getSongs = st.text_input("Enter songs separated by commas:")

        if st.button("Get Songs"):
            songs = [s.strip() for s in getSongs.split(",") if s.strip()]
            for song in songs:
                st.info(f"Searching: {song}")
                options = searchYouTube(song)
                if not options:
                    st.warning(f"No valid result for: {song}")
                    continue
                st.success(f"Downloading: {options[0][0]}")
                downloadYTFromLink(options[0][2], options[0][0])
