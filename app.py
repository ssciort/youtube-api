import os
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
import yt_dlp
from b2sdk.v2 import InMemoryAccountInfo, B2Api

# --- CONFIGURAZIONE ---
API_KEY = "AIzaSyB82mzvzHPClgLi8R6rX60pXy9RnNqhb0k"
DOWNLOAD_FOLDER = "download"
B2_BUCKET_NAME = "downtube"
B2_KEY_ID = "7300fedcec56"
B2_APP_KEY = "003de6e501b93305e9d718ebc4c5fa2b30b1b252f6"
B2_ENDPOINT = "s3.eu-central-003.backblazeb2.com"

# --- INIZIALIZZAZIONE ---
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

app = Flask(__name__)

# Inizializzazione Backblaze B2
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

def search_youtube(query, max_results=10):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    req = youtube.search().list(part="snippet", q=query, type="video", maxResults=max_results)
    res = req.execute()
    return [{"title": item["snippet"]["title"], "video_id": item["id"]["videoId"]} for item in res["items"]]

def download_audio(video_id, title):
    safe_title = "".join(c if c.isalnum() else "_" for c in title)[:80]
    base_path = os.path.join(DOWNLOAD_FOLDER, safe_title)
    mp3_path = f"{base_path}.mp3"
    remote_name = f"{safe_title}.mp3"
    remote_url = f"https://{B2_BUCKET_NAME}.{B2_ENDPOINT}/file/{remote_name}"

    # Controllo se già presente su B2
    try:
        bucket.get_file_info_by_name(remote_name)
        print(f"[INFO] File già esistente su B2: {remote_name}")
        return remote_url
    except Exception:
        pass  # Non trovato, procedo con download

    # Download audio da YouTube
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': base_path + '.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as e:
        print(f"[ERRORE] Download fallito: {e}")
        return None

    if not os.path.exists(mp3_path):
        print("[ERRORE] File MP3 non trovato dopo il download.")
        return None

    # Upload su B2
    try:
        bucket.upload_local_file(
            local_file=mp3_path,
            file_name=remote_name
        )
        print(f"[SUCCESSO] Caricato su B2: {remote_name}")
        return remote_url
    except Exception as e:
        print(f"[ERRORE] Upload su B2 fallito: {e}")
        return None

@app.route("/search")
def search_and_download():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Manca il parametro 'q'"}), 400

    videos = search_youtube(query)
    for video in videos:
        url = download_audio(video["video_id"], video["title"])
        if url:
            return jsonify({"title": video["title"], "url": url})

    return jsonify({"error": "Nessun MP3 disponibile"}), 500

@app.route("/")
def home():
    test_url = request.url_root.rstrip("/") + "/search?q=argomento"
    return f"Benvenuto! Usa <a href='{test_url}'>{test_url}</a> per scaricare l'MP3 da YouTube."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
