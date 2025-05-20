from flask import Flask, request, jsonify
from pytube import Search, YouTube
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "YouTube audio downloader is running!"

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing 'q' parameter"}), 400

    s = Search(query)
    for video in s.results:
        try:
            yt = YouTube(video.watch_url)
            audio = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            if audio:
                return jsonify({
                    "title": yt.title,
                    "url": yt.watch_url,
                    "audio_url": audio.url
                })
        except Exception as e:
            continue

    return jsonify({"error": "No downloadable video found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
