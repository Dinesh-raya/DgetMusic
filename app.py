import streamlit as st
from streamlit_javascript import st_javascript
import json
import yt_dlp
import base64

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

# -------------------- Auth Flow --------------------
if get_from_local_storage("password_correct"):
    authenticated = True
else:
    authenticated = check_password()

if authenticated:
    set_to_local_storage("password_correct", True)

    st.title("🎶 YouTube Music Downloader")
    st.write("Download or listen to music directly from YouTube in audio format (MP3).")
    st.warning("⚠️ This app is for personal use only and not affiliated with YouTube.")

    # -------------------- Helpers --------------------
    def get_binary_file_downloader_html(bin_file, song_title):
        with open(bin_file, 'rb') as f:
            data = f.read()
        bin_str = base64.b64encode(data).decode()
        href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{song_title}.mp3">Download {song_title}</a>'
        return href

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

    def downloadYTFromLink(link, song_title):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'song',
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.cache.remove()
                ydl.download([link])
            st.audio("song.mp3")
            st.markdown(get_binary_file_downloader_html("song.mp3", song_title), unsafe_allow_html=True)
        except yt_dlp.utils.DownloadError as e:
            if "not available" in str(e).lower() or "unavailable" in str(e).lower():
                st.error("⚠️ This song is geo-restricted and unavailable in your region.")
            else:
                st.error(f"Download failed: {e}")
        except Exception as e:
            st.error(f"Error downloading: {e}")

    # -------------------- Tabs --------------------
    tab1, tab2 = st.tabs(["🎧 Download Song", "📦 Batch Download"])

    def is_checkbox_filled():
        return 'songSelection' in st.session_state and st.session_state['songSelection']

    with tab1:
        st.subheader("Download a specific song")

        with st.form("search_form"):
            search = st.text_input("Search for a song or artist:")
            submit_button = st.form_submit_button("Get Relevant Songs")

        if submit_button or is_checkbox_filled():
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
