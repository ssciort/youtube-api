import os
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
import yt_dlp
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.transfer.outbound.upload_source import UploadSourceLocalFile

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

# Backblaze init
info = InMemoryAccountInfo()
b2_api = B2Api(info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

def search_youtube(query, max_results=10):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    request = youtube.search().list(part="snippet", q=query, type="video", maxResults=max_results)
    response = request.execute()
    return [{"title": item["snippet"]["title"], "video_id": item["id"]["videoId"]} for item in response["items"]]

def download_audio(video_id, title):
    safe_title = "".join(c if c.isalnum() else "_" for c in title)
    base_output_path = os.path.join(DOWNLOAD_FOLDER, safe_title)
    mp3_path = f"{base_output_path}.mp3"
    filename_in_b2 = safe_title + ".mp3"

    # Se già caricato su B2
    try:
        file_info = bucket.get_file_info_by_name(filename_in_b2)
        return f"https://{B2_BUCKET_NAME}.{B2_ENDPOINT}/file/{filename_in_b2}"
    except:
        pass

    # Download da YouTube
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': base_output_path + '.%(ext)s',
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
        print(f"Errore nel download: {e}")
        return None

    # Verifica file creato
    if not os.path.exists(mp3_path):
        return None

    # Upload su B2
    try:
        bucket.upload(UploadSourceLocalFile(mp3_path), filename_in_b2)
        print(f"Caricato su B2: {filename_in_b2}")
        return f"https://{B2_BUCKET_NAME}.{B2_ENDPOINT}/file/{filename_in_b2}"
    except Exception as e:
        print(f"Errore upload su B2: {e}")
        return None

@app.route("/search")
def search_and_download():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Manca il parametro 'q'"}), 400

    videos = search_youtube(query)
    for video in videos:
        file_url = download_audio(video["video_id"], video["title"])
        if file_url:
            return jsonify({"title": video["title"], "url": file_url})

    return jsonify({"error": "Nessun video scaricato"}), 500

@app.route("/")
def home():
    full_url = request.url_root.rstrip("/") + "/search?q=argomento"
    return f"Benvenuto! Usa <a href='{full_url}'>{full_url}</a> per scaricare l'MP3 da YouTube."

app.run(host="0.0.0.0", port=3000)
