# Setup Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | v18+ | Required for frontend |
| pnpm | Latest | `npm install -g pnpm` |
| Python | v3.10+ | Required for backend |
| Docker | Latest | Optional — for containerized setup |
| Cohere API Key | — | [console.cohere.com](https://console.cohere.com) |

---

## Environment Variables

### Backend (`backend/.env`)

```env
COHERE_API_KEY=your_cohere_api_key_here
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:3000
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> In production, set `NEXT_PUBLIC_API_URL` to your deployed backend URL (e.g., Render service URL).

---

## Option A — Local Setup (No Docker)

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env              # then fill in COHERE_API_KEY

# Start the server
uvicorn app.main:app --reload --port 8000
```

Backend API docs available at: **http://localhost:8000/docs**

### 2. Frontend

```bash
cd frontend

# Install dependencies
pnpm install

# Start dev server
pnpm run dev
```

Dashboard available at: **http://localhost:3000**

---

## Option B — Docker Compose

```bash
# 1. Create backend env file first
cp backend/.env.example backend/.env
# Edit backend/.env and add your COHERE_API_KEY

# 2. Build and start all services
docker-compose up --build

# 3. To stop
docker-compose down
```

Services:
- Frontend: **http://localhost:3000**
- Backend: **http://localhost:8000**

---

## Project Structure

```
docstribe-ai/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint
│   │   ├── models/               # Pydantic response models
│   │   ├── routers/              # API route handlers
│   │   └── services/
│   │       ├── clinical_rules.py # Cohort & threshold definitions
│   │       ├── cohere_service.py # LLM orchestration & caching
│   │       ├── fallback_engine.py# Deterministic fallback logic
│   │       ├── patient_transformer.py # Payload normalization
│   │       ├── prompt.py         # System prompt
│   │       ├── risk_engine.py    # Deterministic risk overrides
│   │       └── variance_engine.py# Care-path variance rules
│   ├── data/                     # Mock patient JSON files
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                      # Next.js App Router pages
│   ├── components/               # React UI components
│   ├── hooks/                    # Data-fetching hooks (React Query)
│   ├── store/                    # Zustand global state
│   └── package.json
├── docker-compose.yml
├── render.yaml                   # Render deployment blueprint
├── README.md
└── SETUP.md
```

---

## Deployment

### Frontend → Vercel

1. Push repository to GitHub.
2. Import project in [vercel.com](https://vercel.com).
3. Set **Root Directory** to `frontend`.
4. Add environment variable: `NEXT_PUBLIC_API_URL=<your-render-backend-url>`
5. Deploy — Vercel auto-detects Next.js.

### Backend → Render

1. Connect your GitHub repository to [render.com](https://render.com).
2. Select **Blueprint** — Render reads `render.yaml` automatically.
3. Add environment variable: `COHERE_API_KEY=<your-key>`
4. Deploy.

### CORS Configuration

When deploying, update `ALLOWED_ORIGINS` in the backend environment to include your Vercel frontend URL:

```env
ALLOWED_ORIGINS=https://your-app.vercel.app
```

---

## Useful Commands

```bash
# Run backend tests
cd backend && pytest

# Check backend types
cd backend && mypy app/

# Build frontend for production
cd frontend && pnpm build

# Lint frontend
cd frontend && pnpm lint
```
