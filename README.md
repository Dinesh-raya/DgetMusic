# DgetMusic — Final Upgraded (Cookie-free, Pro UI)

This is the final upgraded, lightweight, cloud-friendly version of your Streamlit music app.

Features included:

- Modern UI with thumbnail cards and metadata for search results
- Playlist URL support (expands playlists and lists items)
- Search history stored in session (local to the user)
- Floating mini-player that stays on screen
- Batch mode accepting both names and YouTube URLs (stream + direct download links)
- No cookies, no ffmpeg by default (cloud-friendly)

## Run locally
1. python -m venv venv
2. source venv/bin/activate  # Windows: venv\Scripts\activate
3. pip install -r requirements.txt
4. streamlit run app.py

## Notes
- Playlist expansion and audio extraction is done via yt-dlp without cookies.
- If you need ZIP creation / mp3 conversion, deploy on a server with ffmpeg and re-enable that flow.
