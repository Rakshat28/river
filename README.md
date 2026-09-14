# Riverline Voice Finance Assistant

## Overview

**Riverline** is an empathetic, real-time voice AI financial assistant built with **Next.js**, **Pipecat**, **FastAPI**, and **Daily WebRTC**. It helps users conduct 30-day financial intake conversations, tracks income, essential expenses, optional expenses, and debts with uncertainty confidence tags (`confirmed` | `estimated`), and computes deterministic 30-day cash flow budgets without relying on LLM arithmetic.

---

## Setup

### Prerequisites
- Node.js 20+
- Python 3.12+
- Docker & Docker Compose (for single-command deployment)

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd river
   ```

2. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

---

## Environment Variables

| Variable | Purpose | Required | Default |
|---|---|---|---|
| `DAILY_API_KEY` | Daily.co WebRTC room and meeting token creation | Yes | - |
| `DEEPGRAM_API_KEY` | Deepgram real-time speech-to-text (STT) transcription | Yes | - |
| `CARTESIA_API_KEY` | Cartesia real-time text-to-speech (TTS) audio synthesis | Yes | - |
| `LLM_PROVIDER` | LLM service provider selection (`openai` or `google`) | No | `openai` |
| `OPENAI_API_KEY` | OpenAI API key for function calling & model turn handling | Yes (if `LLM_PROVIDER=openai`) | - |
| `GOOGLE_API_KEY` | Google Gemini API key when using `LLM_PROVIDER=google` | Yes (if `LLM_PROVIDER=google`) | - |
| `NEXT_PUBLIC_AGENT_URL` | Base URL of the agent backend API used by the browser | No | `http://localhost:8000` |

---

## Running the App

### Option 1: Docker Compose (Single Command)
Run the entire application (frontend + agent backend) with a single command:

```bash
docker compose up --build
```

Access the application in your browser:
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Agent FastAPI Backend**: [http://localhost:8000](http://localhost:8000)

### Option 2: Local Development

#### 1. Backend (FastAPI Agent)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r agent/requirements.txt
uvicorn agent.app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend (Next.js App)
```bash
cd frontend
npm install
npm run dev
```

---

## Testing

### Backend Test Suite (Pytest)
Run the complete Python test suite including state, tool handlers, validation, evaluation harness, and deterministic finance engine worked fixtures:

```bash
PYTHONPATH=. .venv/bin/pytest agent/tests -v
```

### Frontend Typechecking
Run strict TypeScript typechecking:

```bash
cd frontend
node_modules/.bin/tsc --noEmit
```
