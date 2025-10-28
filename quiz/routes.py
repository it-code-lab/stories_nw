# app.py
from flask import Flask, render_template, request, jsonify, send_from_directory
import os, json, uuid
from flask import request
import csv, io
from . import quiz_bp  # use the blueprint you defined

# app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
QUIZ_DIR = os.path.join(APP_ROOT, "quizzes")
UPLOAD_DIR = os.path.join(APP_ROOT, "uploads")

os.makedirs(QUIZ_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "audio"), exist_ok=True)

@quiz_bp.post("/import/csv")
def import_csv():
    f = request.files.get('file')
    if not f:
        return {"error":"no file"}, 400
    text = f.stream.read().decode('utf-8', errors='ignore')
    rows = list(csv.DictReader(io.StringIO(text)))
    out = []
    for r in rows:
        t = (r.get('type') or 'mcq').strip().lower()
        base = {
        'id': f"q_{len(out)+1}",
        'type': t,
        'difficulty': (r.get('difficulty') or 'easy').lower(),
        'text': r.get('question') or '',
        'images': [p.strip() for p in (r.get('images') or '').split('|') if p.strip()],
        'timerSec': int(r.get('timerSec') or 0) or None,
        'explanation': r.get('explanation') or ''
    }
    if t=='mcq':
        opts = [r.get('optionA') or '', r.get('optionB') or '', r.get('optionC') or '', r.get('optionD') or '']
        cor = (r.get('correct') or 'A').strip().upper()
        idx = {'A':0,'B':1,'C':2,'D':3}.get(cor,0)
        base.update({'options':opts,'correctIndex':idx})
    else:
        base.update({'answer': r.get('answer') or ''})
        out.append(base)
        return {"questions": out}

@quiz_bp.get("/")
def dashboard():
    return render_template("dashboard.html")

@quiz_bp.get("/builder")
def builder():
    return render_template("builder.html")

@quiz_bp.post("/api/quizzes")
def save_quiz():
    data = request.get_json(force=True)
    qid = data.get("id") or f"quiz_{uuid.uuid4().hex}"
    data["id"] = qid
    with open(os.path.join(QUIZ_DIR, f"{qid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "id": qid})

@quiz_bp.get("/api/quizzes/<qid>")
def get_quiz(qid):
    path = os.path.join(QUIZ_DIR, f"{qid}.json")
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    with open(path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))

@quiz_bp.post("/api/upload")
def upload():
    file = request.files.get("file")
    kind = request.form.get("type", "images")
    dest_dir = os.path.join(UPLOAD_DIR, kind)
    os.makedirs(dest_dir, exist_ok=True)
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    file.save(os.path.join(dest_dir, fname))
    return jsonify({"url": f"/quiz/uploads/{kind}/{fname}"})

@quiz_bp.get("/uploads/<kind>/<fname>")
def serve_upload(kind, fname):
    return send_from_directory(os.path.join(UPLOAD_DIR, kind), fname)

@quiz_bp.get("/play")
def play():
    # Accept ?id=quiz_... or let user choose a local JSON in the UI
    return render_template("player.html")

# if __name__ == "__main__":
#     app.run(debug=True)
