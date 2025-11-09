import streamlit as st
import yt_dlp
import json
import base64
import tempfile
import os
import re
import time
from urllib.parse import urlparse

st.set_page_config(page_title="DgetMusic — Pro", layout="wide")
st.title("🎵 DgetMusic — Stream & Download Audio (Cookie-free, Pro UI)")
st.markdown("Lightweight, cloud-friendly music streamer. No cookies needed.")

def safe_filename(s, max_len=120):
    if not s:
        return "audio"
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    return s[:max_len]

def get_binary_file_downloader_html(bin_file, song_title):
    try:
        with open(bin_file, "rb") as f:
            data = f.read()
    except Exception:
        return ""
    bin_str = base64.b64encode(data).decode()
    safe = safe_filename(song_title)
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{safe}.mp3">⬇️ Download {safe}</a>'
    return href

@st.cache_data(show_spinner=False)
def search_youtube(query):
    ydl_opts = {"quiet": True, "skip_download": True, "noplaylist": True, "default_search": "ytsearch10"}
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries") or []
            for e in entries:
                title = e.get("title")
                vid = e.get("id") or e.get("webpage_url")
                duration = e.get("duration") or 0
                if duration and duration > 60*20:
                    continue
                thumb = None
                if e.get("thumbnails"):
                    thumb = e.get("thumbnails")[-1].get("url")
                results.append({"title": title, "url": f"https://www.youtube.com/watch?v={vid}" if len(str(vid))==11 else vid, "id": vid, "duration": duration, "thumb": thumb})
    except Exception as e:
        st.warning(f"Search failed: {e}")
    return results

def is_youtube_url(text):
    if not text:
        return False
    text = text.strip()
    return "youtube.com/watch" in text or "youtu.be/" in text or "list=" in text

def extract_audio_url(video_url):
    ydl_opts = {"quiet": True, "skip_download": True, "format": "bestaudio/best"}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            formats = info.get("formats") or []
            audio_formats = [f for f in formats if f.get("acodec") and (not f.get("vcodec") or f.get("vcodec") in ("none", ""))]
            if not audio_formats:
                for f in formats:
                    if f.get("url"):
                        return f.get("url"), info.get("title")
                return None, info.get("title")
            best = sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True)[0]
            return best.get("url"), info.get("title")
    except Exception as e:
        return None, None

def expand_playlist(playlist_url):
    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            entries = info.get("entries") or []
            urls = []
            for e in entries:
                vid = e.get("id") or e.get("webpage_url")
                if vid:
                    if len(str(vid))==11:
                        urls.append(f"https://www.youtube.com/watch?v={vid}")
                    else:
                        urls.append(vid)
            return urls
    except Exception as e:
        st.warning(f"Playlist expansion failed: {e}")
        return []

if "history" not in st.session_state:
    st.session_state["history"] = []
if "now_playing" not in st.session_state:
    st.session_state["now_playing"] = {"url": None, "title": None, "thumb": None}

def add_history(q):
    q = q.strip()
    if not q:
        return
    hist = st.session_state["history"]
    if q in hist:
        hist.remove(q)
    hist.insert(0, q)
    st.session_state["history"] = hist[:10]

def show_floating_player(audio_url, title=None, thumb=None):
    safe_title = title or "Now playing"
    thumb_html = f'<img src="{thumb}" style="height:40px;width:40px;border-radius:4px;margin-right:8px;" />' if thumb else ""
    player_html = f'''<div id="dget_floating" style="position:fixed;right:18px;bottom:18px;background:rgba(0,0,0,0.75);color:#fff;padding:8px 12px;border-radius:10px;z-index:9999;display:flex;align-items:center;box-shadow:0 6px 18px rgba(0,0,0,0.35);">{thumb_html}<div style="display:flex;flex-direction:column;min-width:200px;"><div style="font-size:14px;font-weight:600;">{safe_title}</div><audio controls id="dget_audio" style="width:300px;"><source src="{audio_url}" /></audio></div></div>'''
    st.components.v1.html(player_html, height=120, scrolling=False)

st.markdown("## Single Song — Search or Paste URL")
left, right = st.columns([3,1])

with right:
    st.caption("Recent searches (local)")
    for h in st.session_state["history"]:
        if st.button(h, key=f"hist_{h}"):
            st.experimental_set_query_params(q=h)
            st.session_state["_prefill"] = h

with left:
    q = st.text_input("Enter song name or YouTube URL", value=st.session_state.get("_prefill",""))
    search_col1, search_col2 = st.columns([3,1])
    with search_col2:
        go = st.button("Search / Play")
    if go:
        add_history(q)
        if not q or not q.strip():
            st.warning("Please enter a search term or URL.")
        else:
            if "list=" in q or "playlist" in q:
                st.info("Detected playlist — expanding...")
                urls = expand_playlist(q)
                if not urls:
                    st.error("No videos found in playlist or expansion failed.")
                else:
                    st.success(f"Expanded {len(urls)} videos. Showing first 10 for preview.")
                    for u in urls[:10]:
                        aurl, title = extract_audio_url(u)
                        if aurl:
                            st.write(title or u)
                            st.audio(aurl)
                            st.markdown(f'<a href="{aurl}" download="{safe_filename(title)}.mp3">⬇️ Download Audio (Direct)</a>', unsafe_allow_html=True)
                            show_floating_player(aurl, title)
                        else:
                            st.write("Could not extract:", u)
            else:
                if is_youtube_url(q):
                    audio_url, title = extract_audio_url(q)
                    if audio_url:
                        st.success(f"Now playing: {title or q}")
                        st.image(None)
                        st.audio(audio_url)
                        st.markdown(f'<a href="{audio_url}" download="{safe_filename(title or q)}.mp3">⬇️ Download Audio (Direct)</a>', unsafe_allow_html=True)
                        show_floating_player(audio_url, title)
                    else:
                        st.error("Could not extract audio for this URL.")
                else:
                    results = search_youtube(q)
                    if not results:
                        st.warning("No search results.")
                    else:
                        for idx, r in enumerate(results[:5], start=1):
                            st.markdown(f"### {idx}. {r['title']}")
                            cols = st.columns([1,3,1])
                            with cols[0]:
                                if r.get("thumb"):
                                    st.image(r["thumb"], width=120)
                            with cols[1]:
                                st.write(f"Duration: {int(r.get('duration',0)//60)}:{int(r.get('duration',0)%60):02d}")
                                if st.button(f"Play {idx}", key=f"play_{idx}_{r['id']}"):
                                    aurl, title = extract_audio_url(r["url"])
                                    if aurl:
                                        st.success(f"Now playing: {title}")
                                        st.audio(aurl)
                                        st.markdown(f'<a href="{aurl}" download="{safe_filename(title)}.mp3">⬇️ Download Audio (Direct)</a>', unsafe_allow_html=True)
                                        show_floating_player(aurl, title)
                                    else:
                                        st.error("Could not extract audio from this result.")

st.markdown("---")
st.markdown("## Batch Download / Stream (comma-separated names or URLs)")
batch_input = st.text_area("Enter names or YouTube URLs separated by commas:", height=140, placeholder="name1, name2, https://youtu.be/abcd, name3")
play_all = st.checkbox("Play all sequentially (in-page)", value=False)
do_zip = False

if st.button("Process Batch"):
    items = [it.strip() for it in (batch_input or "").split(",") if it.strip()]
    if not items:
        st.warning("Provide at least one name or URL.")
    else:
        for i, it in enumerate(items, start=1):
            st.markdown(f"### {i}. {it}")
            if is_youtube_url(it):
                url = it
            else:
                res = search_youtube(it)
                if not res:
                    st.warning(f"No result for: {it}")
                    continue
                url = res[0]["url"] if isinstance(res[0], dict) else res[0][2]
            audio_url, title = extract_audio_url(url)
            if audio_url:
                st.write(f"**{title or it}**")
                if play_all:
                    st.audio(audio_url)
                else:
                    st.audio(audio_url)
                st.markdown(f'<a href="{audio_url}" download="{safe_filename(title or it)}.mp3">⬇️ Download Audio (Direct)</a>', unsafe_allow_html=True)
                show_floating_player(audio_url, title or it)
            else:
                st.error(f"Could not extract audio for: {it}")

st.markdown("---")
st.info("This lightweight Pro UI is cookie-free and cloud-friendly. For restricted videos, cookies or OAuth are required which are intentionally disabled in this build.")