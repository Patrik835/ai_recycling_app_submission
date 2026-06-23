# Recycler — AI Waste Identifier

A mobile-responsive web app that photographs a waste item, classifies its material using CLIP, and generates location-specific disposal instructions via a local LLM (Ollama).

---

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.10+ |
| Ollama | 0.30+ |
| llama3 model | pulled via `ollama pull llama3` |

Python packages are listed in `requirements.txt` and installed into a virtual environment.

---

## First-time setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd ai_recycling_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Ollama

Download from [https://ollama.com](https://ollama.com) and install for your OS.

Then pull the LLM model (4.7 GB, one-time download):

```bash
ollama pull llama3
```

---

## Running the app

You need **two terminals** running simultaneously.

### Terminal 1 — Ollama (LLM server)

```bash
ollama serve
```

Keep this running. Ollama must be active for disposal instructions and the AI chat to work.

### Terminal 2 — Backend + Frontend

```bash
cd ai_recycling_app/backend
source ../venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

On startup the backend will:
- Pre-load the CLIP material classification model (~400 MB, cached after first run)
- Warm up the Ollama connection

Then open your browser at:

```
http://localhost:8000
```

---

## Accessing from a phone

Make sure your phone is on the **same Wi-Fi network** as your laptop.

Find your laptop's local IP:

```bash
ip addr show | grep 'inet ' | grep -v 127
```

Then open Safari/Chrome on your phone and go to:

```
http://<your-laptop-ip>:8000
```

> **Note:** Camera access (`getUserMedia`) requires HTTPS or `localhost`. On a phone over plain HTTP, use the **Gallery** button to upload a photo instead, or use `ngrok` to get an HTTPS tunnel:
> ```bash
> ngrok http 8000
> ```

---

## GPU acceleration (optional)

By default the app runs on CPU. If you have an NVIDIA GPU, install the matching PyTorch CUDA build for faster CLIP inference:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Replace `cu128` with your CUDA version (check with `nvidia-smi`).

---

## Running tests

```bash
cd ai_recycling_app
source venv/bin/activate
pytest tests/
```

---

## Project structure

```
ai_recycling_app/
├── backend/
│   ├── main.py              # FastAPI app, routes, static file serving
│   ├── controller.py        # Scan pipeline orchestration
│   ├── material.py          # CLIP zero-shot material classification
│   ├── detection.py         # Detection stub (CLIP is primary classifier)
│   ├── llm_orchestrator.py  # Ollama client, prompt building
│   ├── knowledge_base.py    # Local recycling rules per country
│   ├── database.py          # SQLite scan history
│   ├── preprocessing.py     # Image validation and resizing
│   ├── location.py          # GPS / country code resolution
│   ├── models.py            # Pydantic data models
│   └── data/
│       ├── rules/           # JSON recycling rules per country
│       └── recycling.db     # SQLite database (auto-created)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
├── docs/                    # Architecture and requirements docs
└── requirements.txt
```
