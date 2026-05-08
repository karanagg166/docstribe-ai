# Docstribe AI - OPD Clinical Dashboard

Docstribe is an LLM-powered OPD (Outpatient Department) Clinical Dashboard designed to transform raw clinical notes and patient records into structured, actionable insights. By leveraging Cohere's large language models combined with deterministic clinical rules, the platform helps doctors and care coordinators prioritize patients, track care path variances, and manage clinical conversions.

## Architecture

The project is structured as a modern full-stack web application:

- **Frontend**: Next.js (App Router), React, Tailwind CSS v4, Framer Motion, Recharts, Zustand, React Query.
- **Backend**: FastAPI, Python, Cohere API for LLM extraction, deterministic Risk & Variance engines.
- **Database/Cache**: Currently uses file-based caching and mock JSON, designed to seamlessly scale to a PostgreSQL/Neon database.

## Features

- **LLM-Powered Extraction**: Extracts structured insights (risks, progressions, cohorts) directly from unstructured clinical notes.
- **Risk Stratification**: Hybrid risk engine combining AI insights with strict deterministic clinical rules.
- **Care Path Variance Detection**: Automatically flags deviations from standard care paths (e.g., medication escalations, overdue actions).
- **Patient Worklist & Filtering**: Real-time filtering of patient cohorts, risk levels, and clinical statuses.
- **Clinical Funnel Analytics**: Visualizes the conversion pipeline from initial consultation to treatment conversion.

## Getting Started

### Prerequisites
- Node.js (v18+)
- pnpm
- Python (v3.10+)
- Docker (optional, for containerized deployment)
- Cohere API Key

### Running Locally (Without Docker)

**1. Start the Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create an .env file
echo "COHERE_API_KEY=your_api_key_here" > .env
echo "APP_ENV=development" >> .env
echo "ALLOWED_ORIGINS=http://localhost:3000" >> .env

uvicorn app.main:app --reload --port 8000
```

**2. Start the Frontend:**
```bash
cd frontend
pnpm install
pnpm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000) and the backend API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### Running Locally (With Docker)

```bash
# Add your Cohere API key to backend/.env first
docker-compose up --build
```

## Deployment

### Frontend (Vercel)
1. Push the repository to GitHub.
2. Import the project into Vercel.
3. Set the Root Directory to `frontend`.
4. Vercel will automatically detect the Next.js framework and deploy it.

### Backend (Render)
The repository includes a `render.yaml` blueprint for easy deployment to Render.
1. Connect your GitHub repository to Render.
2. Select "Blueprint" and it will automatically provision the FastAPI web service.
3. Ensure you set the `COHERE_API_KEY` in the Render dashboard environment variables.
