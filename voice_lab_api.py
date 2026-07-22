#!/usr/bin/env python3
"""
통암송 성경낭독 등록 실험실 — 비공개 테스트 API (특허 출원 전 내부 테스트용)
직접 녹음한 성경 본문 음성을 등록·재생·관리. nginx Basic Auth로 /voice-lab/, /voice-lab-api/ 보호.
"""
from flask import Flask, request, jsonify, send_file, abort
import json
import os
import time
import uuid

app = Flask(__name__)

BASE = "/var/www/tong/voice-lab/data"
AUDIO_DIR = os.path.join(BASE, "audio")
MANIFEST_PATH = os.path.join(BASE, "manifest.json")

EXT_BY_MIME = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        return []
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(items):
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, MANIFEST_PATH)


@app.route("/voice-lab-api/list", methods=["GET"])
def list_items():
    items = load_manifest()
    items.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
    return jsonify(items)


@app.route("/voice-lab-api/upload", methods=["POST"])
def upload():
    ref = (request.form.get("ref") or "").strip()
    text = (request.form.get("text") or "").strip()
    translation = (request.form.get("translation") or "").strip()
    note = (request.form.get("note") or "").strip()
    audio = request.files.get("audio")
    if not ref:
        return jsonify(error="본문 표기(ref)를 입력해 주세요"), 400
    if not audio:
        return jsonify(error="녹음 파일이 없습니다"), 400

    ext = EXT_BY_MIME.get(audio.mimetype, "webm")
    item_id = uuid.uuid4().hex[:12]
    filename = f"{item_id}.{ext}"
    audio.save(os.path.join(AUDIO_DIR, filename))

    items = load_manifest()
    entry = {
        "id": item_id,
        "ref": ref,
        "text": text,
        "translation": translation,
        "note": note,
        "filename": filename,
        "mime": audio.mimetype,
        "createdAt": int(time.time() * 1000),
        "primary": False,
    }
    items.append(entry)
    save_manifest(items)
    return jsonify(entry)


@app.route("/voice-lab-api/primary/<item_id>", methods=["POST"])
def set_primary(item_id):
    items = load_manifest()
    target = next((x for x in items if x["id"] == item_id), None)
    if not target:
        return jsonify(error="not found"), 404
    for x in items:
        if x["ref"] == target["ref"]:
            x["primary"] = (x["id"] == item_id)
    save_manifest(items)
    return jsonify(ok=True)


@app.route("/voice-lab-api/delete/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    items = load_manifest()
    target = next((x for x in items if x["id"] == item_id), None)
    if not target:
        return jsonify(error="not found"), 404
    items = [x for x in items if x["id"] != item_id]
    save_manifest(items)
    try:
        os.remove(os.path.join(AUDIO_DIR, target["filename"]))
    except OSError:
        pass
    return jsonify(ok=True)


@app.route("/voice-lab-api/audio/<item_id>", methods=["GET"])
def get_audio(item_id):
    items = load_manifest()
    target = next((x for x in items if x["id"] == item_id), None)
    if not target:
        abort(404)
    path = os.path.join(AUDIO_DIR, target["filename"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype=target.get("mime", "audio/webm"))


if __name__ == "__main__":
    os.makedirs(AUDIO_DIR, exist_ok=True)
    app.run(host="127.0.0.1", port=8093, threaded=True)
