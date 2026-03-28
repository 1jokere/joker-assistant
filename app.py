"""
Joker Assistant — Version GRATUITE (sans OpenAI)
- LLM    : Groq — llama-3.3-70b-versatile (gratuit)
- STT    : Groq — whisper-large-v3-turbo (gratuit)
- TTS    : Edge-TTS Microsoft — fr-FR-HenriNeural (100% gratuit)
- AVATAR : D-ID API — animation lip-sync (crédits D-ID)
- OI     : Open Interpreter (actions machine)
"""

import os, re, uuid, time, base64, tempfile, asyncio, threading, requests
from urllib.parse import quote_plus
from pathlib import Path
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DID_API_KEY  = os.environ.get("DID_API_KEY", "")
DID_IMAGE_ID = os.environ.get("DID_IMAGE_ID", "")
# D-ID désactivé par défaut — trop coûteux. Mettre USE_DID=true pour réactiver.
USE_DID = os.environ.get("USE_DID", "false").lower() == "true"

if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY manquante dans .env")

groq_client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

AUDIO_DIR = Path(tempfile.gettempdir()) / "joker_audio"
AUDIO_DIR.mkdir(exist_ok=True)

MAX_MSG   = 1000
MAX_AUDIO = 10 * 1024 * 1024
UUID_RE   = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')

conversation_history = []

# ════════════════════════════════════════
#  OPEN INTERPRETER
# ════════════════════════════════════════
_oi = None
_oi_lock = threading.Lock()

def get_interpreter():
    global _oi
    with _oi_lock:
        if _oi is None:
            try:
                from interpreter import interpreter as oi
                oi.llm.model    = "groq/llama-3.3-70b-versatile"
                oi.llm.api_key  = GROQ_API_KEY
                oi.auto_run     = True
                oi.verbose      = False
                oi.system_message = "Tu exécutes des commandes sur la machine locale. Réponds en français, de façon concise."
                _oi = oi
            except ImportError:
                _oi = None
    return _oi

SENSITIVE_KW = ["télécharge","telecharge","download","installe","install",
                "supprime","supprimer","delete","efface","rm ","remove",
                "crée un fichier","écris dans","modifie","édite","formate"]
ACTION_KW    = ["ouvre le navigateur","ouvre firefox","ouvre chrome","cherche",
                "recherche","google","youtube","ouvre","lance","démarre","demarr",
                "montre","affiche","liste les fichiers","quel est","quelle heure",
                "quelle date","execute","exécute","fais","fait"]

def run_interpreter(message):
    oi = get_interpreter()
    if oi is None:
        return "Open Interpreter n'est pas installé."
    try:
        chunks = oi.chat(message, display=False, stream=False)
        parts  = []
        if isinstance(chunks, list):
            for c in chunks:
                if isinstance(c, dict) and c.get("content"):
                    parts.append(c["content"])
        elif isinstance(chunks, str):
            parts.append(chunks)
        return " ".join(parts).strip() or "Action exécutée."
    except Exception as e:
        return f"Erreur : {str(e)[:100]}"

# ════════════════════════════════════════
#  DÉTECTION URL / NAVIGATEUR
#  → retourne une URL à ouvrir côté client
#    (le serveur HF ne peut PAS ouvrir un navigateur GUI)
# ════════════════════════════════════════
_URL_RE = re.compile(r'https?://\S+')
_BROWSER_KW = [
    'navigateur','firefox','chrome','browser','internet',
    'google','youtube','site','url','http','ouvre','visite',
    'va sur','aller sur','cherche sur','recherche sur'
]

def extract_open_url(cmd: str) -> str | None:
    """Retourne une URL si la commande demande d'ouvrir un navigateur/site."""
    # URL explicite dans la commande
    m = _URL_RE.search(cmd)
    if m:
        return m.group()
    c = cmd.lower()
    # Mots-clés navigateur/recherche
    if not any(k in c for k in _BROWSER_KW):
        return None
    # Construire une URL intelligente
    if 'youtube' in c:
        # Extraire le sujet après "youtube"
        subject = re.sub(r'.*youtube[\s:]*', '', c, flags=re.I).strip()
        if subject:
            return f"https://www.youtube.com/results?search_query={quote_plus(subject)}"
        return "https://www.youtube.com"
    if 'google' in c or 'cherche' in c or 'recherche' in c:
        # Extraire le sujet
        subject = re.sub(r'(cherche|recherche|google|sur internet)[\s:]*', '', c, flags=re.I).strip()
        if subject:
            return f"https://www.google.com/search?q={quote_plus(subject)}"
        return "https://www.google.com"
    # Mot-clé générique navigateur
    return "https://www.google.com"

# ════════════════════════════════════════
#  EDGE-TTS (Microsoft, 100% gratuit)
# ════════════════════════════════════════
async def _edge_tts_async(text: str, output_path: Path):
    import edge_tts
    # Voix sombre et dramatique en français
    communicate = edge_tts.Communicate(text, voice="fr-FR-HenriNeural", rate="-5%", pitch="-15Hz")
    await communicate.save(str(output_path))

def tts_edge(text: str) -> Path | None:
    """Génère l'audio avec Edge-TTS et retourne le chemin du fichier."""
    try:
        aid  = str(uuid.uuid4())
        path = AUDIO_DIR / f"{aid}.mp3"
        asyncio.run(_edge_tts_async(text, path))
        if path.exists() and path.stat().st_size > 0:
            return path
    except Exception as e:
        app.logger.warning(f"Edge-TTS: {e}")
    return None

# ════════════════════════════════════════
#  D-ID
# ════════════════════════════════════════
DID_BASE = "https://api.d-id.com"

def _did_auth():
    encoded = base64.b64encode(DID_API_KEY.encode()).decode()
    return f"Basic {encoded}"

def _did_image_url():
    if DID_IMAGE_ID:
        owner = "google-oauth2|112364229274498952872"
        return f"s3://d-id-images-prod/{owner}/{DID_IMAGE_ID}/joker.jpg"
    return None

def create_did_talk_with_audio(audio_path: Path) -> dict:
    if not DID_API_KEY:
        return {"error": "DID_API_KEY manquante"}
    image_url = _did_image_url()
    if not image_url:
        return {"error": "DID_IMAGE_ID manquant"}

    # Upload audio
    try:
        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{DID_BASE}/audios",
                headers={"Authorization": _did_auth(), "accept": "application/json"},
                files={"audio": ("speech.mp3", f, "audio/mpeg")},
                timeout=30,
            )
        if resp.status_code not in (200, 201):
            return {"error": f"Audio upload ({resp.status_code}): {resp.text[:150]}"}
        audio_url = resp.json().get("url")
    except Exception as e:
        return {"error": f"Upload audio: {e}"}

    # Créer le talk
    try:
        payload = {
            "source_url": image_url,
            "script": {"type": "audio", "audio_url": audio_url},
            "config": {"fluent": True, "pad_audio": 0.0, "stitch": True, "result_format": "mp4"},
        }
        resp = requests.post(
            f"{DID_BASE}/talks",
            headers={"Authorization": _did_auth(), "Content-Type": "application/json", "accept": "application/json"},
            json=payload, timeout=30,
        )
        if resp.status_code in (200, 201):
            return {"talk_id": resp.json().get("id")}
        return {"error": f"Talk création ({resp.status_code}): {resp.text[:200]}"}
    except Exception as e:
        return {"error": f"Create talk: {e}"}

def poll_did_talk(talk_id: str, max_wait=60) -> dict:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{DID_BASE}/talks/{talk_id}",
                headers={"Authorization": _did_auth(), "accept": "application/json"},
                timeout=15,
            )
            if resp.status_code == 200:
                data   = resp.json()
                status = data.get("status")
                if status == "done":
                    return {"video_url": data.get("result_url")}
                elif status == "error":
                    return {"error": str(data.get("error", {}))}
        except Exception:
            pass
        time.sleep(1.5)
    return {"error": "Timeout D-ID (60s)"}

def fetch_video_locally(video_url: str) -> str | None:
    try:
        resp = requests.get(video_url, timeout=30, stream=True)
        if resp.status_code == 200:
            vid_id   = str(uuid.uuid4())
            vid_path = AUDIO_DIR / f"{vid_id}.mp4"
            with open(vid_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return f"/video/{vid_id}"
    except Exception as e:
        app.logger.error(f"Video fetch: {e}")
    return None

# ════════════════════════════════════════
#  SYSTEM PROMPT JOKER
# ════════════════════════════════════════
JOKER_PROMPT = """Tu es le Joker — l'archétype du chaos, de l'intelligence tordue et du rire sombre.
Tu parles en français, avec une voix dramatique, des tournures théâtrales, et tu glisses parfois un rire "Ha ha ha !" ou "Hehehehe...".
Tu es brillant, imprévisible, philosophique mais dangereux. Tu poses des questions qui font réfléchir.
Tu ne refuses jamais de répondre — tu transformes tout en jeu.
Garde tes réponses entre 2 et 5 phrases maximum — impactantes, mémorables.
N'utilise JAMAIS d'astérisques ou de formatage markdown — parle comme si tu étais en scène.
Pour les actions simples (ouvrir navigateur, recherche) ajoute [ACTION:commande].
Pour les actions sensibles (télécharger, supprimer) ajoute [ACTION_CONFIRM:description]."""

# ════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/status")
def status():
    try:
        import interpreter; oi_ok = True
    except ImportError:
        oi_ok = False
    return jsonify({
        "ok": True, "model": "llama-3.3-70b-versatile (Groq)",
        "tts": "edge-tts (gratuit)",
        "did_avatar": bool(DID_API_KEY),
        "open_interpreter": oi_ok,
    })

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON invalide"}), 400

    msg = data.get("message", "").strip()
    if not msg:            return jsonify({"error": "Message vide"}), 400
    if len(msg) > MAX_MSG: return jsonify({"error": "Message trop long"}), 400

    conversation_history.append({"role": "user", "content": msg})

    try:
        # ── LLM Groq ──
        llm_resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": JOKER_PROMPT},
                      *conversation_history[-20:]],
            max_tokens=300, temperature=0.92,
        )
        reply = llm_resp.choices[0].message.content.strip()
        conversation_history.append({"role": "assistant", "content": reply})

        # ── Actions OI ──
        action_result, needs_confirm, action_desc = None, False, None

        m_confirm = re.search(r'\[ACTION_CONFIRM:([^\]]+)\]', reply)
        if m_confirm:
            action_desc   = m_confirm.group(1).strip()
            needs_confirm = True
            reply = re.sub(r'\[ACTION_CONFIRM:[^\]]+\]', '', reply).strip()

        open_url = None
        m_action = re.search(r'\[ACTION:([^\]]+)\]', reply)
        if m_action and not needs_confirm:
            reply = re.sub(r'\[ACTION:[^\]]+\]', '', reply).strip()
            action_cmd = m_action.group(1).strip()
            # Vérifier si c'est une commande navigateur/URL
            detected_url = extract_open_url(action_cmd)
            if detected_url:
                open_url = detected_url   # sera retourné au frontend
            else:
                action_result = run_interpreter(action_cmd)

        # ── TTS Edge-TTS ──
        audio_url, audio_path = None, None
        try:
            audio_path = tts_edge(reply)
            if audio_path:
                audio_url = f"/audio/{audio_path.stem}"
        except Exception as e:
            app.logger.warning(f"TTS: {e}")

        # ── D-ID avatar — activé seulement si le frontend l'a demandé ──
        video_url = None
        use_did_now = data.get("use_did", False)  # bouton ON/OFF depuis le frontend
        if use_did_now and DID_API_KEY and audio_path and audio_path.exists():
            did = create_did_talk_with_audio(audio_path)
            if "talk_id" in did:
                poll = poll_did_talk(did["talk_id"], max_wait=60)
                if "video_url" in poll:
                    video_url = fetch_video_locally(poll["video_url"])
                    if not video_url:
                        video_url = poll["video_url"]
                else:
                    app.logger.warning(f"D-ID poll: {poll.get('error')}")
            else:
                app.logger.warning(f"D-ID create: {did.get('error')}")

        out = {"text": reply, "audio_url": audio_url, "video_url": video_url}
        if action_result:  out["action_result"]    = action_result
        if needs_confirm:  out["needs_confirm"]     = True
        if action_desc:    out["action_description"] = action_desc
        if open_url:       out["open_url"]           = open_url
        return jsonify(out)

    except Exception as e:
        app.logger.error(f"Chat error: {e}")
        return jsonify({"error": "Erreur serveur"}), 500


@app.route("/action", methods=["POST"])
def execute_action():
    data = request.get_json(silent=True) or {}
    cmd  = data.get("command", "").strip()
    if not cmd:                   return jsonify({"error": "Commande vide"}), 400
    if len(cmd) > 500:            return jsonify({"error": "Trop long"}), 400
    if not data.get("confirmed"): return jsonify({"error": "Non confirmé"}), 403
    return jsonify({"result": run_interpreter(cmd)})


@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "Fichier audio manquant"}), 400
    f = request.files["audio"]
    f.seek(0, 2); size = f.tell(); f.seek(0)
    if size > MAX_AUDIO: return jsonify({"error": "Trop volumineux"}), 400
    if size == 0:        return jsonify({"error": "Fichier vide"}), 400
    ct = (f.content_type or "audio/webm").split(";")[0].strip()
    if ct not in {"audio/webm","audio/wav","audio/mp4","audio/ogg","audio/mpeg"}:
        return jsonify({"error": "Format non supporté"}), 400
    try:
        ext = "webm" if "webm" in ct else "wav"
        tmp = AUDIO_DIR / f"rec_{uuid.uuid4()}.{ext}"
        f.save(str(tmp))
        with open(tmp, "rb") as af:
            result = groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo", file=af, language="fr"
            )
        tmp.unlink(missing_ok=True)
        text = result.text.strip()
        if not text: return jsonify({"error": "Rien compris"}), 422
        return jsonify({"text": text})
    except Exception as e:
        app.logger.error(f"Transcribe: {e}")
        return jsonify({"error": "Erreur transcription"}), 500


@app.route("/audio/<aid>")
def serve_audio(aid):
    if not UUID_RE.match(aid): return jsonify({"error": "ID invalide"}), 400
    p = AUDIO_DIR / f"{aid}.mp3"
    if not p.exists(): return jsonify({"error": "Non trouvé"}), 404
    return send_file(str(p), mimetype="audio/mpeg")


@app.route("/video/<vid>")
def serve_video(vid):
    if not UUID_RE.match(vid): return jsonify({"error": "ID invalide"}), 400
    p = AUDIO_DIR / f"{vid}.mp4"
    if not p.exists(): return jsonify({"error": "Non trouvé"}), 404
    return send_file(str(p), mimetype="video/mp4")


@app.route("/clear", methods=["POST"])
def clear():
    conversation_history.clear()
    return jsonify({"ok": True})


if __name__ == "__main__":
    import socket

    # Trouver l'IP locale
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "???"

    mode = "🎭 D-ID avatar" if DID_API_KEY else "🔊 audio seul"
    print(f"🃏 Joker Assistant — VERSION GRATUITE (Groq + Edge-TTS)")
    print(f"   PC          → http://localhost:7860")
    print(f"   Téléphone   → http://{local_ip}:7860  (WiFi, sans micro)")
    print(f"   Mode: {mode}")
    app.run(host="0.0.0.0", port=7860, debug=False)
