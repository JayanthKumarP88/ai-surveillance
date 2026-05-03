# CHIMERA — AI Surveillance & Threat Analysis

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)
![React](https://img.shields.io/badge/React-19-61dafb.svg)
![Leaflet](https://img.shields.io/badge/Leaflet-Interactive_Maps-199900.svg)
![PIL](https://img.shields.io/badge/Pillow-Image_Forensics-FFD43B.svg)

## Overview

**Chimera** is a real-time AI surveillance and threat analysis platform that generates randomized news reports, uses AI to analyse potential security threats in specific areas, and provides rapid police response capabilities. It features AI-based image checking, a dynamic map to highlight convoy routes, and automated redirection based on live threat intelligence.

The system simulates a full OSINT (Open Source Intelligence) pipeline — from synthetic social media post generation to protest detection, coordination cluster analysis, deepfake forensics, and dynamic convoy route planning.

## Key Features

### 📊 Threat Dashboard
- **Synthetic Data Generation** — Generates realistic social media posts (120+ per batch) across 10 Indian metro cities with configurable modes: `baseline`, `escalation`, and `coordination`.
- **Protest Escalation Detection** — Multi-signal scoring engine that evaluates volume spikes, negative sentiment shifts, violence keyword density, and media surge rates to produce a 0–100 threat score (`baseline` → `moderate` → `high` → `critical`).
- **Coordination / Bot Cluster Detection** — Identifies suspicious bot networks using Jaccard similarity, MD5 content fingerprinting, duplicate ratios, account age analysis, and follower/following anomalies.
- **OPSEC & Disinformation Scanner** — Flags posts containing misinformation indicators (`FAKE_DISINFORMATION`) or operational security leaks (`SENSITIVE_OPSEC`) with automated dossier generation.
- **Risk Classification** — Categorizes posts into `HIGH` and `MILD` risk tiers based on weighted scoring of violence terminology, mobilization language, coordination jargon, and infrastructure targeting.

### 🗺️ Live Threat Map (Leaflet)
- **Interactive India Map** — Plots all generated posts as geo-tagged markers on a Leaflet map.
- **Threat Zone Visualization** — High-risk posts rendered as large red radius circles to indicate danger zones.
- **Dynamic Convoy Routing** — Planned route (Delhi → Jaipur → Ahmedabad → Surat → Mumbai → Pune → Hyderabad → Bangalore) with automatic safe-route bypass generation when threats intersect waypoints.
- **Route Comparison** — Visual overlay of planned route (blue/red) vs. computed safe route (green).

### 🧪 Image Forensics
- **GAN Deepfake Detector** — Scores images 0–100 using edge density analysis, bright/dark extreme fractions, RGB channel imbalance, and blockiness proxy (downscale→upscale RMS diff).
- **PRNU Camera Fingerprinting** — Register device sensor noise patterns from multiple images, then match unknown images to registered cameras via pseudo-noise correlation.

### 📁 Automated Dossier Generation
- One-click feed scanning produces JSON dossier files with full evidence trails, analyst attribution, and per-post verdicts.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (CRA)                     │
│   Dashboard ┊ Live Map (Leaflet) ┊ Forensics ┊ Social Feed  │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend (Uvicorn)                   │
│                                                               │
│  /synthetic/posts         — Generate synthetic intelligence   │
│  /detect/protest          — Protest escalation scoring        │
│  /detect/coordination     — Bot cluster detection             │
│  /analyze/auto            — OPSEC & disinformation analysis   │
│  /forensics/ganfinger     — GAN deepfake scoring              │
│  /forensics/prnu/*        — Camera fingerprint register/match │
│  /narrative/generate      — Counter-narrative drafting        │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Leaflet, react-leaflet |
| Backend | Python, FastAPI, Uvicorn |
| Image Forensics | Pillow (PIL) — edge detection, histogram analysis, PRNU |
| Maps | Leaflet.js with CARTO tile layers |
| Data Models | Pydantic v2 |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- pip / npm

### 1. Clone the Repository

```bash
git clone https://github.com/jayanth-kumar-morem/chimera.git
cd chimera
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install fastapi uvicorn pillow pydantic
uvicorn app:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm start
```

The frontend will open at `http://localhost:3000` and connect to the backend at `http://127.0.0.1:8000`.

## Usage

1. **Generate Intelligence** — Select a scenario mode (`baseline` / `escalation` / `coordination`), set the post count (e.g. 120), and click **Generate**.
2. **Analyze Threats** — Click **Detect Protest** to run the escalation scorer, or **Detect Coordination** to identify bot clusters.
3. **Scan for OPSEC / Fakes** — Click **Scan Feed** to auto-flag disinformation and operational security leaks, with automatic dossier export.
4. **View Live Map** — Switch to the **Live Map** tab to see geo-plotted posts, threat zones, and dynamic convoy routing.
5. **Forensics** — Switch to the **Forensics** tab to run GAN deepfake scoring or PRNU camera fingerprinting on uploaded images.

## Project Structure

```
chimera/
├── backend/
│   ├── app.py                 # FastAPI backend (all endpoints)
│   └── dossiers/              # Auto-generated dossier JSON files
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main React application
│   │   ├── App.css            # Styling (Arctic Light UI)
│   │   └── index.js           # Entry point
│   ├── public/
│   └── package.json
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + timestamp |
| `POST` | `/synthetic/posts` | Generate synthetic social media posts |
| `POST` | `/detect/protest` | Run protest escalation detector |
| `POST` | `/detect/coordination` | Run coordination/bot cluster detector |
| `POST` | `/analyze/auto` | OPSEC & disinformation auto-scanner |
| `POST` | `/forensics/ganfinger/score` | GAN deepfake image scoring |
| `POST` | `/forensics/prnu/register` | Register camera PRNU fingerprint |
| `POST` | `/forensics/prnu/match` | Match image to registered cameras |
| `POST` | `/narrative/generate` | Generate counter-narrative drafts |

## License

This project is for educational and demonstration purposes.
