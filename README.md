# 🃏 Joker Assistant

Un assistant vocal IA thématique **Joker** — voix dramatique en français, animation lip-sync, reconnaissance vocale, et capable d'ouvrir des sites web sur commande.

> Déployable gratuitement sur [Hugging Face Spaces](https://huggingface.co/spaces) en moins de 10 minutes.

---

## Ce que fait le Joker

- 🧠 **Répond** avec la personnalité du Joker — dramatique, philosophique, imprévisible
- 🎤 **Comprend ta voix** — reconnaissance vocale Whisper (Groq, gratuit)
- 🔊 **Parle** avec une voix sombre et grave (Edge-TTS Microsoft, 100% gratuit)
- 🌐 **Ouvre des sites** sur commande vocale — YouTube, Google, n'importe quelle URL
- 🎭 **Animation lip-sync** D-ID optionnelle (bouton ON/OFF pour gérer les crédits)

---

## Technologies utilisées

| Fonction | Service | Coût |
|---|---|---|
| LLM (cerveau) | [Groq](https://groq.com) — LLaMA 3.3 70B | Gratuit |
| Voix (STT) | Groq — Whisper large-v3-turbo | Gratuit |
| Synthèse vocale (TTS) | Edge-TTS Microsoft — fr-FR-HenriNeural | Gratuit |
| Avatar lip-sync | [D-ID](https://www.d-id.com) | ~20 crédits/mois gratuits |
| Hébergement | [Hugging Face Spaces](https://huggingface.co/spaces) | Gratuit |

---

## Déploiement sur Hugging Face Spaces

### 1. Créer un compte Hugging Face
Rends-toi sur [huggingface.co](https://huggingface.co) et crée un compte gratuit.

### 2. Créer un nouveau Space
- Clique sur ton profil → **New Space**
- Donne-lui un nom (ex: `joker-assistant`)
- Choisis **Docker** comme SDK
- Visibilité : **Public**

### 3. Cloner le Space en local
```bash
git clone https://huggingface.co/spaces/TON_USERNAME/joker-assistant
cd joker-assistant
```

### 4. Copier les fichiers du projet
Copie dans le dossier cloné :
- `app.py`
- `index.html`
- `requirements.txt`
- `Dockerfile`

### 5. Configurer les clés API (Secrets)
Dans les **Settings** de ton Space → **Repository secrets**, ajoute :

| Nom du secret | Où l'obtenir |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys |
| `DID_API_KEY` | [studio.d-id.com](https://studio.d-id.com) → API (optionnel) |
| `DID_IMAGE_ID` | ID de ton image uploadée sur D-ID (optionnel) |

> ⚠️ Ne mets **jamais** tes clés API directement dans le code ou dans un fichier `.env` sur GitHub.

### 6. Pousser les fichiers
```bash
git add .
git commit -m "Initial deploy"
git push
```

Le Space se construit automatiquement (~2 minutes). Ton Joker est en ligne à :
`https://TON_USERNAME-joker-assistant.hf.space`

---

## Utilisation locale (sur ton PC)

### Prérequis
- Python 3.11+
- pip

### Installation
```bash
git clone https://github.com/1jokere/joker-assistant.git
cd joker-assistant
pip install -r requirements.txt
```

### Configuration
Crée un fichier `.env` à la racine (**ne jamais commiter ce fichier**) :
```
GROQ_API_KEY=ta_clé_groq
DID_API_KEY=ta_clé_did        # optionnel
DID_IMAGE_ID=ton_image_id     # optionnel
```

### Lancement
```bash
python app.py
```

Ouvre ton navigateur sur : `http://localhost:7860`

---

## Activer le micro sur téléphone (local)

Pour utiliser le micro depuis ton téléphone sur le réseau local, installe ngrok :
```bash
pip install pyngrok
```
Le script détecte automatiquement ngrok et affiche l'URL HTTPS dans le terminal.

---

## Activer l'animation D-ID

L'animation lip-sync D-ID est **désactivée par défaut** pour ne pas consommer de crédits.

Dans l'interface, utilise le bouton **🎥 Animation D-ID : OFF/ON** pour l'activer quand tu veux.

Chaque réponse animée consomme **1 crédit** D-ID. Le plan gratuit offre ~20 crédits/mois.

---

## Structure du projet

```
joker-assistant/
├── app.py           # Backend Flask (LLM, TTS, D-ID, actions)
├── index.html       # Frontend (interface Joker, audio, animation)
├── requirements.txt # Dépendances Python
├── Dockerfile       # Pour Hugging Face Spaces
└── README.md
```

---

## Crédits

Construit avec ❤️ et un peu de chaos.  
Propulsé par [Groq](https://groq.com), [Edge-TTS](https://github.com/rany2/edge-tts), [D-ID](https://www.d-id.com) et [Hugging Face](https://huggingface.co).
