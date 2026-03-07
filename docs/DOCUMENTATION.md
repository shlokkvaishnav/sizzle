# Sizzle — Technical Documentation

**Version:** 1.0  
**Last updated:** 2025

This document describes the Sizzle restaurant copilot application: system requirements, installation, configuration, architecture, API, feature usage, and troubleshooting. It is intended for developers and operators.

---

## Table of contents

1. [Overview](#1-overview)
2. [System requirements](#2-system-requirements)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Running the application](#5-running-the-application)
6. [Architecture](#6-architecture)
7. [API reference](#7-api-reference)
8. [Feature usage](#8-feature-usage)
9. [Troubleshooting](#9-troubleshooting)
10. [Generating a PDF](#10-generating-a-pdf)

---

## 1. Overview

Sizzle is a restaurant management and revenue intelligence application with the following capabilities:

- **Revenue analytics:** Contribution margins, popularity and velocity, BCG-style menu matrix, hidden-star detection, combo suggestions, and price recommendations. All computed from database data; combo engine trains on order history automatically.
- **Voice ordering:** Speech-to-text (local Whisper), intent and item extraction (rule-based plus optional LLM via Ollama), disambiguation, session cart, and text-to-speech (Edge TTS, cloud).
- **Web call:** Browser-based call flow: WebSocket audio stream, backend pipeline, agent TTS; order can be confirmed from the call.
- **Operations:** Orders, tables (floor plan, seat, settle), menu items, inventory, reports, settings.

Backend: FastAPI, SQLAlchemy, PostgreSQL. Frontend: React, Vite. Voice STT and LLM run locally; TTS uses Microsoft Edge TTS (external).

---

## 2. System requirements

### Required

| Component   | Version / note |
|------------|-----------------|
| Python     | 3.10 or 3.11    |
| Node.js    | 18.x or 20.x LTS |
| npm        | Bundled with Node |
| Git        | Recent          |
| PostgreSQL | 14 or higher, or hosted (e.g. Supabase, Neon) |

### Optional

| Component | Purpose |
|----------|---------|
| Redis    | Voice session store. If unset, in-memory or database-backed sessions are used. |
| Ollama   | Local LLM for voice router and brain. If disabled, rule-based and FAISS-based flow is used. |
| FFmpeg   | Audio conversion for the voice pipeline. Required for non-WAV input. |

### Database

A PostgreSQL instance is required. The application creates tables and applies schema migrations on startup. Provide a connection URI; no manual SQL is required for the default schema. Supabase and Neon are supported (use pooler URI on port 5432 where applicable).

---

## 3. Installation

### 3.1 Clone the repository

```bash
git clone <repository-url>
cd pet-pooja
```

### 3.2 Backend

From the project root:

```bash
cd backend
```

Create and activate a virtual environment:

- **Windows (PowerShell or CMD):**
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

Create `.env` from the example (see Section 4) and set at least `DATABASE_URL`.

Install dependencies:

```bash
pip install -r requirements.txt
```

First run may download models (e.g. Whisper, sentence-transformers). Ensure a stable connection and sufficient disk space.

Seed the database (safe to run multiple times; uses get-or-create logic):

```bash
python seed_database.py
```

### 3.3 Frontend

From the project root, in a new terminal:

```bash
cd frontend
npm install
```

Optional: create `frontend/.env` and set `VITE_API_BASE_URL` if the backend is not at `http://localhost:8000`.

---

## 4. Configuration

### 4.1 Backend environment (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and set the following.

**Required:**

| Variable       | Description |
|----------------|-------------|
| DATABASE_URL   | PostgreSQL connection string. Use scheme `postgresql://` (not `postgres://`) for SQLAlchemy. Example: `postgresql://user:password@host:5432/dbname`. |

**Optional:**

| Variable           | Default                  | Description |
|--------------------|--------------------------|-------------|
| REDIS_URL          | (none)                   | Redis URL for voice sessions, e.g. `redis://localhost:6379/0`. |
| AUTH_ENABLED       | false                    | Set to true to enable JWT login. |
| JWT_SECRET         | (none)                   | Secret for JWT; minimum 32 characters if auth is enabled. |
| JWT_ALGORITHM      | HS256                    | JWT algorithm. |
| CORS_ORIGINS       | localhost:5173, 3000     | Comma-separated allowed origins. |

**Voice / STT:**

| Variable           | Default          | Description |
|--------------------|------------------|-------------|
| WHISPER_MODEL      | large-v3-turbo   | Whisper model when GPU is available. |
| WHISPER_CPU_MODEL  | small            | Whisper model when only CPU is available. |
| STT_MIN_CONFIDENCE | 0.45             | Minimum transcript confidence; below this the user may be asked to repeat. |
| STT_VAD_FILTER     | true             | Use Whisper built-in VAD to skip silence. |

**Voice / TTS:**

| Variable         | Default | Description |
|------------------|---------|-------------|
| TTS_ENABLED      | true    | Enable Edge TTS. If false, only text is returned; frontend may use browser TTS. |
| TTS_OUTPUT_FORMAT| mp3     | Output format for synthesized audio. |

**Voice / LLM (Ollama):**

| Variable              | Default                 | Description |
|-----------------------|-------------------------|-------------|
| LLM_ENABLED           | true                    | Enable LLM for voice. |
| LLM_BASE_URL          | http://localhost:11434  | Ollama API base URL. |
| LLM_MODEL             | qwen2.5:7b-instruct-q4_K_M | Model for response generation. |
| LLM_ROUTER_ENABLED    | true                    | Use LLM for intent and item extraction. |
| LLM_ROUTER_MODEL      | qwen2.5:1.5b            | Model for router (lighter). |
| LLM_ROUTER_TIMEOUT_SEC| 5.0                     | Timeout for router requests. |

### 4.2 Frontend environment

| Variable             | Default (with Vite proxy) | Description |
|----------------------|---------------------------|-------------|
| VITE_API_BASE_URL    | /api                      | Backend API base. In dev, Vite proxies `/api` to the backend; for a different backend set e.g. `http://localhost:8000/api`. |

---

## 5. Running the application

### 5.1 Two terminals (recommended for development)

**Terminal 1 — Backend:**

```bash
cd backend
# Activate venv if not already
python main.py
```

Server listens on `http://0.0.0.0:8000`. Check `http://localhost:8000/health` for a healthy response.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Vite typically serves at `http://localhost:5173`. Open that URL in a browser.

### 5.2 Windows single command

From the project root:

```cmd
start.bat
```

This starts the backend, waits for health, then starts the frontend and may open a browser. The script opens `http://localhost:3000` by default; if your Vite config uses port 5173, use that URL instead.

---

## 6. Architecture

### 6.1 High-level

- **Backend:** FastAPI application. Mount points: `/api/auth`, `/api/ops`, `/api/revenue`, `/api/voice`. Database and optional Redis are used for persistence; voice pipeline uses in-memory or persisted session state.
- **Frontend:** Single-page React app (Vite). Communicates with backend via REST and, for Web call, WebSocket.
- **Voice:** Audio is sent to the backend; STT (faster-whisper) runs locally; optional Ollama LLM runs locally; TTS (Edge TTS) uses Microsoft’s service. Pipeline: STT, normalizer, intent/item extraction (regex + FAISS + optional LLM), session cart update, response generation, TTS.

### 6.2 Backend layout

- `main.py`: FastAPI app, CORS, lifespan, route mounting, health.
- `database.py`: SQLAlchemy engine, session factory, base.
- `models.py`: ORM models (restaurants, categories, menu items, orders, tables, voice sessions, combo suggestions, etc.).
- `api/routes_auth.py`: Login, JWT, user/restaurant context.
- `api/routes_ops.py`: Orders, tables, menu items, inventory, reports, settings.
- `api/routes_revenue.py`: Dashboard, menu matrix, hidden stars, risks, combos, price recommendations, trends, analytics, ML endpoints.
- `api/routes_voice.py`: Transcribe, process-audio, process (text), speak, confirm-order, voice orders; WebSocket stream for Web call.
- `modules/revenue/`: contribution_margin, popularity, menu_matrix, hidden_stars, combo_engine, bundle_pricer, price_optimizer, analyzer, trends.
- `modules/voice/`: stt (faster-whisper), pipeline, llm_router, llm_brain, llm_response, item_matcher, session_store, tts, tts_engine_indic (Edge TTS).

### 6.3 Data flow (voice)

1. Client sends audio (or text) to `/voice/process-audio` or `/voice/process`.
2. Audio is converted to 16 kHz mono WAV if needed; Whisper produces transcript.
3. Pipeline: normalizer, intent classification, item extraction (FAISS + optional LLM), quantity/modifier extraction, disambiguation handling, session cart update.
4. Response text is generated (templates or LLM); TTS produces audio (Edge TTS or fallback).
5. Response includes items, session_order, session_items, and TTS payload for the client.

### 6.4 Combo engine

Combo suggestions are produced from order history: basket matrix from recent orders, Pearson/Phi correlation for item pairs and triples, scoring and filtering, optional ML bundle pricing, then persistence to the database. Training runs automatically when combos are requested and the store is empty or a retrain is requested. No separate “train” step is required; the “Refresh Combos” action triggers regeneration when needed.

---

## 7. API reference

Base URL: `http://localhost:8000` (or your backend host). All revenue and voice routes are under `/api/revenue` and `/api/voice`; ops under `/api/ops`; auth under `/api/auth`. Query parameter `restaurant_id` is used where multi-tenant context is required.

### 7.1 Health

- **GET /health** — Liveness/readiness. Returns JSON with status.

### 7.2 Auth (`/api/auth`)

- **POST /api/auth/login** — Authenticate; returns JWT and user/restaurant info when auth is enabled.
- **GET /api/auth/me/{restaurant_id}** — Current user for restaurant (when auth enabled).
- **PATCH /api/auth/me/{restaurant_id}** — Update user/restaurant (when auth enabled).

### 7.3 Revenue (`/api/revenue`)

- **GET /api/revenue/dashboard** — Dashboard metrics (revenue, orders, health, hidden stars count, risks, etc.).
- **GET /api/revenue/menu-matrix** — BCG matrix items (margin, popularity, quadrant).
- **GET /api/revenue/hidden-stars** — Hidden star items (high margin, low visibility).
- **GET /api/revenue/risks** — Items at risk (e.g. low margin and/or low popularity).
- **GET /api/revenue/combos** — Combo suggestions. Query: `force_retrain` (bool), `restaurant_id`. Response includes `combos` and `ml_summary` (orders used, pricing model, etc.).
- **POST /api/revenue/combos/retrain** — Trigger background combo retrain.
- **POST /api/revenue/combos/{combo_id}/promote** — Promote a combo to the menu.
- **GET /api/revenue/price-recommendations** — Price change recommendations.
- **GET /api/revenue/category-breakdown** — Category-level breakdown.
- **GET /api/revenue/analyze** — Full analysis payload (margins, popularity, matrix, hidden stars, health).
- **GET /api/revenue/margins** — Contribution margin list.
- **GET /api/revenue/popularity** — Popularity/velocity list.
- **GET /api/revenue/trends** — Trend data (e.g. item trends, quadrant drift).
- **GET /api/revenue/ml/status** — ML pipeline status.
- **POST /api/revenue/ml/train** — Trigger ML pipeline training.
- **GET /api/revenue/ml/aov** — AOV insights.
- **GET /api/revenue/ml/demand** — Demand forecasts (query: `days_ahead`).
- **GET /api/revenue/ml/upsell** — Upsell candidates (query: `item_ids`, `top_k`).
- **GET /api/revenue/ml/predictions** — Aggregated ML predictions.

### 7.4 Voice (`/api/voice`)

- **POST /api/voice/transcribe** — Submit audio; returns transcript and language.
- **POST /api/voice/process-audio** — Full pipeline from audio: STT, NLP, cart, response, TTS. Body: form data with `audio`, `session_id`, optional `language`, `restaurant_id`.
- **POST /api/voice/process** — Same pipeline from text. Body: JSON with `text`, `session_id`, optional `restaurant_id`.
- **POST /api/voice/speak** — TTS only. Body: JSON with `text`, `language`.
- **POST /api/voice/confirm-order** — Confirm order from session. Body: order payload and KOT info.
- **GET /api/voice/orders** — Voice-order history.
- **WebSocket** — Used for Web call streaming (path and usage as implemented in `routes_voice.py` and frontend).

### 7.5 Operations (`/api/ops`)

- **GET /api/ops/orders** — List orders (query: status, restaurant_id, etc.).
- **GET /api/ops/orders/{order_id}** — Order detail.
- **POST /api/ops/orders** — Create order.
- **PATCH /api/ops/orders/{order_id}** — Update order.
- **POST /api/ops/orders/{order_id}/cancel** — Cancel order.
- **GET /api/ops/tables** — Tables (floor plan, state).
- **PATCH /api/ops/tables/{table_id}** — Update table.
- **POST /api/ops/tables/{table_id}/book** — Book table.
- **POST /api/ops/tables/{table_id}/settle** — Settle table.
- **POST /api/ops/tables/{table_id}/seat** — Seat table.
- **GET /api/ops/menu-items** — Menu items.
- **PATCH /api/ops/menu-items/{item_id}/price** — Update item price.
- **POST /api/ops/tables/{table_id}/add-item** — Add item to table order.
- **GET /api/ops/inventory** — Inventory list.
- **POST /api/ops/inventory/adjust** — Adjust stock.
- **GET /api/ops/reports** — Reports.
- **GET /api/ops/settings** — Settings.
- **PATCH /api/ops/settings** — Update settings.

---

## 8. Feature usage

### 8.1 Dashboard

Route: `/dashboard`. Summary of today’s revenue, orders, average order value, menu health, hidden stars count, risks, quadrant drift. Data is loaded from the revenue API and reflects current database state.

### 8.2 Menu analysis

Route: `/dashboard/menu-analysis`. BCG-style matrix (Stars, Plowhorses, Puzzles, Dogs), contribution margin and profitability tables, popularity/velocity table, price opportunities. Matrix and margins use ML-derived fields (e.g. quadrant confidence, profitability score) when available. Price opportunities show recommendations and, when returned by the API, ML opportunity scores.

### 8.3 Hidden stars

Route: `/dashboard/hidden-stars`. Items with high contribution margin and low visibility; ML confidence and velocity trend are shown when returned by the API. Used to identify promotion opportunities.

### 8.4 Combo engine

Route: `/dashboard/combos`. Combo suggestions from order-history correlation; training runs on the backend when needed. “Refresh Combos” triggers regeneration. Combo Insights tab shows orders used, correlation pairs, combos saved, pricing model (ML or rule-based), and per-combo confidence, lift, and support. No separate “Train ML” action; training is automatic.

### 8.5 Voice order

Route: `/dashboard/voice-order`. User can speak or type. Backend runs STT (if audio), intent and item extraction, disambiguation when needed, and updates the session cart. Response is shown and optionally played via TTS. Cart is additive; disambiguation adds only the chosen item and does not replace the cart.

### 8.6 Web call

Route: `/dashboard/web-call`. Simulated call: start call, speak, agent responds with TTS, items are added to the cart. Order can be placed from the call. Only the agent voice is played; duplicate voices on end/start call have been addressed in the codebase. Disambiguation keeps prior cart items and adds only the selected variant.

### 8.7 Orders, tables, inventory, reports, settings

- **Orders:** List and filter orders; view details; create, update, cancel.
- **Tables:** View floor plan; book, seat, add items, settle. Settle resolves the table’s current order and clears the table.
- **Inventory:** View and adjust ingredient stock.
- **Reports:** Revenue and operational reports.
- **Settings:** Application and restaurant settings.

---

## 9. Troubleshooting

### Backend does not start: DATABASE_URL is not set

Create `backend/.env` from `backend/.env.example` and set `DATABASE_URL` to a valid PostgreSQL URI (`postgresql://...`).

### Backend: ModuleNotFoundError (e.g. psycopg2, faster_whisper)

Activate the virtual environment and run `pip install -r requirements.txt` from the `backend` directory.

### Backend: relation or schema does not exist

Run the backend once; it applies migrations. For a new database, ensure it is empty or correctly targeted. Then run `python seed_database.py` from `backend` if you need seed data.

### Seed: duplicate key or unique violation

The seed script uses get-or-create by slug (and similar) for restaurants, categories, menu items, tables. If duplicates persist, check the reported table and constraint; you may need to remove conflicting rows or fix the seed data.

### Frontend: blank page or API errors

Confirm the backend is running and reachable. With the Vite dev server, `/api` is proxied to the backend. If the backend is on another host or port, set `VITE_API_BASE_URL` in `frontend/.env`.

### Voice: no or poor speech recognition

Ensure `faster-whisper` is installed and the first run has completed (model download). Check backend logs for STT errors. On CPU-only systems, the smaller model (e.g. `small`) is used by default; set `WHISPER_CPU_MODEL` if needed.

### Voice: no TTS playback

If TTS is enabled, Edge TTS requires network access to Microsoft’s service. If TTS is disabled, the UI still shows the agent text; the frontend may use browser TTS as fallback. Verify `TTS_ENABLED` and network/firewall.

### Web call: cart replaced after disambiguation

The pipeline is designed to merge the chosen disambiguation item into the existing cart, not replace it. If replacement occurs, ensure you are on the latest backend and frontend; clear cache and restart. If the LLM returns items not in the disambiguation options, the backend filters them out to avoid wrong additions.

### Port 8000 or 5173 already in use

Stop the process using that port or change the port in the backend (`main.py`) or frontend (Vite config and proxy).

### Combo engine returns no combos

Combos are generated from order history. If there are no orders or too few, the list may be empty or use fallback logic. Run the seed script to add sample orders, then use “Refresh Combos” on the Combo Engine page. Check backend logs for combo pipeline errors.

---

## 10. Generating a PDF

This document is written in Markdown. To produce a PDF:

**Using Pandoc (recommended):**

```bash
pandoc docs/DOCUMENTATION.md -o docs/DOCUMENTATION.pdf --pdf-engine=xelatex -V geometry:margin=1in
```

If you do not have a LaTeX distribution, use a HTML intermediate:

```bash
pandoc docs/DOCUMENTATION.md -o docs/DOCUMENTATION.html -s --metadata title="Sizzle Technical Documentation"
```

Then open the HTML in a browser and use Print to PDF.

**Using a Markdown-to-PDF tool:**

Many editors and CLI tools (e.g. md-to-pdf, grip, VS Code extensions) can convert this file to PDF. Use the same file: `docs/DOCUMENTATION.md`.

---

*End of document.*
