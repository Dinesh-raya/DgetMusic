# app.py
import streamlit as st
import yt_dlp
import re
import tempfile
import os
from urllib.parse import urlparse

st.set_page_config(page_title="DgetMusic — Pro (Final)", layout="wide")
st.title("🎵 DgetMusic — Pro (Final) — Search, Stream & Download (Cookie-free)")

# -------------------- Utilities --------------------
def safe_filename(s, max_len=120):
    if not s:
        return "audio"
    s = re.sub(r'[\\/*?:"<>|]', "_", str(s))
    return s[:max_len]

def is_youtube_url(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return ("youtube.com/watch" in t) or ("youtu.be/" in t) or ("list=" in t)

# -------------------- yt-dlp wrappers --------------------
@st.cache_data(show_spinner=False)
def search_youtube(query: str):
    """
    Return list of dicts: {title, url, id, duration, thumb}
    """
    ydl_opts = {"quiet": True, "skip_download": True, "noplaylist": True, "default_search": "ytsearch10"}
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries") or []
            for e in entries:
                title = e.get("title") or "Untitled"
                vid = e.get("id") or e.get("webpage_url")
                duration = e.get("duration") or 0
                # skip very long videos (optional)
                if duration and duration > 60 * 60:  # 60 minutes guard
                    continue
                thumb = None
                try:
                    if e.get("thumbnails"):
                        thumb = e.get("thumbnails")[-1].get("url")
                except Exception:
                    thumb = None
                # canonical url
                url = None
                try:
                    if vid and len(str(vid)) == 11:
                        url = f"https://www.youtube.com/watch?v={vid}"
                    else:
                        url = e.get("webpage_url") or str(vid)
                except Exception:
                    url = str(vid)
                results.append({"title": title, "url": url, "id": vid, "duration": duration, "thumb": thumb})
    except Exception as e:
        st.warning(f"Search failed: {e}")
    return results

def extract_audio_url(video_url: str):
    """
    Extract a direct audio stream URL (best available).
    Returns (audio_url, title) or (None, None)
    """
    ydl_opts = {"quiet": True, "skip_download": True, "format": "bestaudio/best"}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get("title") or video_url
            formats = info.get("formats") or []
            # prefer audio-only formats (vcodec none)
            audio_formats = [
                f for f in formats
                if f.get("url") and f.get("acodec") and (not f.get("vcodec") or f.get("vcodec") in ("none", ""))
            ]
            if audio_formats:
                best = sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True)[0]
                return best.get("url"), title
            # fallback any format
            for f in formats:
                if f.get("url"):
                    return f.get("url"), title
            return None, title
    except Exception:
        return None, None

def expand_playlist(playlist_url: str):
    """
    Expand a playlist URL into a list of video URLs (cookie-free).
    """
    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            entries = info.get("entries") or []
            urls = []
            for e in entries:
                vid = e.get("id") or e.get("webpage_url")
                if not vid:
                    continue
                if len(str(vid)) == 11:
                    urls.append(f"https://www.youtube.com/watch?v={vid}")
                else:
                    urls.append(e.get("webpage_url") or str(vid))
            return urls
    except Exception as e:
        st.warning(f"Playlist expansion failed: {e}")
        return []

# -------------------- Session state defaults --------------------
if "last_results" not in st.session_state:
    st.session_state["last_results"] = []          # list of dict results from last search
if "history" not in st.session_state:
    st.session_state["history"] = []               # last 10 queries
if "selected_result_index" not in st.session_state:
    st.session_state["selected_result_index"] = None  # index (1..5) of expanded result
if "selected_custom" not in st.session_state:
    st.session_state["selected_custom"] = None     # for direct URL play (dict with url/title/thumb)

def add_history(q: str):
    q = (q or "").strip()
    if not q:
        return
    hist = st.session_state["history"]
    if q in hist:
        hist.remove(q)
    hist.insert(0, q)
    st.session_state["history"] = hist[:10]

# -------------------- UI: Top layout --------------------
st.markdown("## Single Song — Search or Paste URL")
col_left, col_right = st.columns([3, 1])

with col_right:
    st.caption("Recent searches (local)")
    for h in st.session_state["history"]:
        if st.button(h, key=f"hist_{h}"):
            # prefill search box by setting query param and session prefill
            st.session_state["_prefill"] = h

with col_left:
    q = st.text_input("Enter song name or paste YouTube URL", value=st.session_state.get("_prefill", ""))
    c1, c2 = st.columns([4, 1])
    with c2:
        pressed = st.button("Search / Play")

    if pressed:
        add_history(q)
        # reset previous selection (but keep last_results if we want)
        st.session_state["selected_result_index"] = None
        st.session_state["selected_custom"] = None

        if not q or not q.strip():
            st.warning("Please enter a search term or URL.")
        else:
            # Playlist URL handling
            if "list=" in q or "playlist" in q:
                st.info("Detected playlist URL — expanding...")
                urls = expand_playlist(q)
                if not urls:
                    st.error("No videos found in playlist or expansion failed.")
                else:
                    # convert to results list for presentation (first 10)
                    new_results = []
                    for u in urls[:10]:
                        # try to get title & thumb lightly (without heavy operations)
                        aurl, title = extract_audio_url(u)
                        new_results.append({"title": title or u, "url": u, "id": None, "duration": None, "thumb": None})
                    st.session_state["last_results"] = new_results
            else:
                # If direct YouTube URL -> show as a single custom selectable item (but also perform regular search if desired)
                if is_youtube_url(q):
                    # Put the URL as a single custom selected item and also keep last_results empty (or attempt a search)
                    # We'll set selected_custom so we can expand it directly in-place
                    st.session_state["last_results"] = []  # clear prior results if any
                    st.session_state["selected_result_index"] = None
                    st.session_state["selected_custom"] = {"url": q, "title": None, "thumb": None}
                else:
                    # normal search by query
                    results = search_youtube(q)
                    # store only up to 5 results for UI
                    st.session_state["last_results"] = results[:5]

# -------------------- Render last results (keeps them visible) --------------------
results = st.session_state.get("last_results") or []

if results:
    st.markdown("### Search Results")
    for idx, r in enumerate(results, start=1):
        st.markdown(f"**{idx}. {r.get('title','Untitled')}**")
        row_cols = st.columns([1, 4, 1])
        with row_cols[0]:
            if r.get("thumb"):
                st.image(r.get("thumb"), width=120)
        with row_cols[1]:
            dur = r.get("duration") or 0
            if dur:
                st.write(f"Duration: {int(dur//60)}:{int(dur%60):02d}")
            else:
                st.write("Duration: -")
            st.write("")  # spacing
        with row_cols[2]:
            # clicking sets the selected_result_index (persisted across reruns)
            btn_key = f"play_btn_{idx}_{str(r.get('id'))}"
            if st.button("Play", key=btn_key):
                st.session_state["selected_result_index"] = idx
                # clear custom
                st.session_state["selected_custom"] = None

        # If this result is the selected one, render expanded player box inline (Option B look)
        if st.session_state.get("selected_result_index") == idx:
            # extract audio URL and display boxed player
            st.markdown("")  # small spacer
            aurl, title = extract_audio_url(r.get("url"))
            if aurl:
                # highlight box
                st.markdown(
                    f"""
                    <div style="border-radius:10px;padding:12px;border:1px solid #ddd;background:#f9fafb;">
                      <div style="display:flex;align-items:center;">
                        <div style="flex:0 0 auto;margin-right:12px;">
                          {'<img src=\"'+ (r.get('thumb') or '') + '\" style=\"width:96px;height:54px;object-fit:cover;border-radius:6px;\">' if r.get('thumb') else ''}
                        </div>
                        <div style="flex:1 1 auto;">
                          <div style="font-size:16px;font-weight:700;margin-bottom:6px;">{title or r.get('title')}</div>
                          <div style=\"margin-bottom:8px;\">
                            <audio controls style=\"width:100%;\">
                              <source src=\"{aurl}\">
                              Your browser does not support the audio element.
                            </audio>
                          </div>
                          <div>
                            <a href="{aurl}" download="{safe_filename(title or r.get('title'))}.mp3">⬇️ Download Audio (Direct)</a>
                          </div>
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.error("Could not extract audio for this item.")

# -------------------- If user pasted a direct URL (selected_custom) show it as its own expanded box ----------
if st.session_state.get("selected_custom"):
    sc = st.session_state["selected_custom"]
    # attempt extraction once when set
    aurl, title = extract_audio_url(sc.get("url"))
    if aurl:
        st.markdown("### Direct URL — Play")
        st.markdown(
            f"""
            <div style="border-radius:10px;padding:12px;border:1px solid #ddd;background:#f9fafb;">
              <div style="display:flex;align-items:center;">
                <div style="flex:0 0 auto;margin-right:12px;">
                  <!-- no thumb for direct unless found -->
                </div>
                <div style="flex:1 1 auto;">
                  <div style="font-size:16px;font-weight:700;margin-bottom:6px;">{title or sc.get('url')}</div>
                  <div style=\"margin-bottom:8px;\">
                    <audio controls style=\"width:100%;\">
                      <source src=\"{aurl}\">
                      Your browser does not support the audio element.
                    </audio>
                  </div>
                  <div>
                    <a href="{aurl}" download="{safe_filename(title or sc.get('url'))}.mp3">⬇️ Download Audio (Direct)</a>
                  </div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error("Could not extract audio for the pasted URL.")
    # clear selected_custom so it doesn't re-run repeatedly unless user presses Search again with same URL
    st.session_state["selected_custom"] = None

st.markdown("---")

# -------------------- Batch mode (names / URLs mixed) --------------------
st.markdown("## Batch Download / Stream (comma-separated names or URLs)")
batch_input = st.text_area("Enter names or YouTube URLs separated by commas:", height=140,
                           placeholder="name1, name2, https://youtu.be/abcd, name3")
play_all = st.checkbox("Play all sequentially (players shown in order)", value=False)
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
                url = res[0].get("url")
            aurl, title = extract_audio_url(url)
            if aurl:
                st.write(f"**{title or it}**")
                # inline player only
                st.audio(aurl)
                st.markdown(f'<a href="{aurl}" download="{safe_filename(title or it)}.mp3">⬇️ Download Audio (Direct)</a>',
                            unsafe_allow_html=True)
            else:
                st.error(f"Could not extract audio for: {it}")

st.markdown("---")
st.info(
    "This build is cookie-free and cloud-friendly. It shows 5 search results and expands the selected result inline with a highlighted player (thumbnail + title). "
    "Restricted/login-required videos are not accessible without cookies or OAuth."
)
