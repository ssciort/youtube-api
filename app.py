import os
from flask import Flask, request, jsonify, send_from_directory
from googleapiclient.discovery import build
import yt_dlp

API_KEY = "AIzaSyB82mzvzHPClgLi8R6rX60pXy9RnNqhb0k"
DOWNLOAD_FOLDER = "download"

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

app = Flask(__name__)

def search_youtube(query, max_results=10):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    request = youtube.search().list(part="snippet", q=query, type="video", maxResults=max_results)
    response = request.execute()
    return [{"title": item["snippet"]["title"], "video_id": item["id"]["videoId"]} for item in response["items"]]

def download_audio(video_id, title):
    safe_title = "".join(c if c.isalnum() else "_" for c in title)
    base_output_path = os.path.join(DOWNLOAD_FOLDER, safe_title)
    mp3_path = f"{base_output_path}.mp3"

    if os.path.exists(mp3_path):
        return mp3_path  # già scaricato

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
        print(f"Errore nel download di {title}: {e}")
        return None

    # Verifica se il file mp3 è stato generato
    if os.path.exists(mp3_path):
        return mp3_path
    else:
        # Cancella eventuali file .webm, .m4a, ecc.
        for ext in ['webm', 'm4a', 'opus']:
            original_path = f"{base_output_path}.{ext}"
            if os.path.exists(original_path):
                try:
                    os.remove(original_path)
                    print(f"File temporaneo cancellato: {original_path}")
                except Exception as e:
                    print(f"Errore nella cancellazione di {original_path}: {e}")
        return None


@app.route("/search")
def search_and_download():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Manca il parametro 'q'"}), 400

    videos = search_youtube(query)
    for video in videos:
        path = download_audio(video["video_id"], video["title"])
        if path:
            file_url = request.url_root + f"download/{os.path.basename(path)}"
            return jsonify({"title": video["title"], "url": file_url})

    return jsonify({"error": "Nessun video scaricato"}), 500

@app.route("/download/<filename>")
def serve_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename)

@app.route("/")
def home():
    #return "Benvenuto! Usa /search?q=argomento per scaricare l'MP3 da YouTube."
    full_url = request.url_root.rstrip("/") + "/search?q=argomento"
    return f"Benvenuto! Usa <a href='{full_url}'>{full_url}</a> per scaricare l'MP3 da YouTube."

app.run(host="0.0.0.0", port=3000)
