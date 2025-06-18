import os
import random
import traceback
import tempfile
import base64
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch
import yt_dlp
from pydub import AudioSegment
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

played_tracks = []
played_tracks_data = []

# === UTILITAIRES ===

def get_random_track(playlist_url):
    try:
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        results = sp.playlist_tracks(playlist_id)
        tracks = [t for t in results['items'] if t['track']]
    except Exception as e:
        raise Exception("Erreur Spotify : " + str(e))

    if not tracks:
        raise Exception("Playlist vide ou non accessible.")

    remaining = [t for t in tracks if t['track']['id'] not in played_tracks]
    if not remaining:
        played_tracks.clear()
        remaining = tracks

    track = random.choice(remaining)['track']
    played_tracks.append(track['id'])

    title = track['name']
    artist = track['artists'][0]['name']
    return f"{title} {artist}", title, artist

def download_youtube_audio(query, output_path):
    search = VideosSearch(query, limit=1)
    result = search.result()

    if not result['result']:
        raise Exception("Aucun résultat YouTube.")

    video = result['result'][0]
    link = video['link']
    title = video['title']
    thumbnail = video['thumbnails'][0]['url']
    channel = video['channel']['name']

    print(f"[YOUTUBE] Vidéo trouvée : {link}")

    cookie_b64 = os.getenv("YTDLP_COOKIES_BASE64", "").strip()
    if not cookie_b64:
        raise Exception("Variable YTDLP_COOKIES_BASE64 absente ou vide.")

    with tempfile.NamedTemporaryFile(delete=False, mode="wb", suffix=".txt") as tmp_cookie_file:
        tmp_cookie_file.write(base64.b64decode(cookie_b64))
        tmp_cookie_path = tmp_cookie_file.name

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.splitext(output_path)[0] + '.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'cookiefile': tmp_cookie_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
    finally:
        os.remove(tmp_cookie_path)

    if not os.path.exists(output_path):
        raise Exception(f"Échec du téléchargement : {output_path} introuvable.")

    return output_path, title, thumbnail, channel

def cut_audio(input_path, output_path, duration_sec):
    audio = AudioSegment.from_file(input_path)
    if len(audio) < duration_sec * 1000:
        raise Exception("Extrait trop court.")
    start = random.randint(0, len(audio) - duration_sec * 1000)
    audio[start:start + duration_sec * 1000].export(output_path, format="mp3")

# === ROUTES ===

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/play")
def play():
    try:
        duration = int(request.args.get("duration", 3))
        full = request.args.get("full", "false").lower() == "true"
        playlist_url = request.args.get("playlist", "https://open.spotify.com/playlist/4YHLZ2DTFg6vGKbJMFsRPG")

        temp_dir = tempfile.gettempdir()
        original_path = os.path.join(temp_dir, "original_audio.mp3")
        extrait_path = os.path.join("static", "extrait.mp3")

        for path in (original_path, extrait_path):
            if os.path.exists(path):
                os.remove(path)

        full_query, title, artist = get_random_track(playlist_url)
        original_path, yt_title, thumbnail_url, channel = download_youtube_audio(full_query, original_path)

        if full:
            shutil.copy(original_path, extrait_path)
        else:
            cut_audio(original_path, extrait_path, duration)

        played_tracks_data.insert(0, {
            "title": title,
            "artist": artist,
            "thumbnail": thumbnail_url,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        played_tracks_data[:] = played_tracks_data[:10]

        return jsonify({
            "success": True,
            "filename": extrait_path,
            "audio_url": "/" + extrait_path,
            "title": title,
            "artist": artist,
            "thumbnail": thumbnail_url
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/history")
def history():
    return jsonify(played_tracks_data)

@app.route("/envcheck")
def envcheck():
    return jsonify({
        "SPOTIPY_CLIENT_ID": bool(SPOTIPY_CLIENT_ID),
        "SPOTIPY_CLIENT_SECRET": bool(SPOTIPY_CLIENT_SECRET)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
