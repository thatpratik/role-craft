# Tech Stack

## Architecture

Hybrid — Next.js handles UI only, FastAPI handles all processing and AI. Two services, cleanly separated.

```
Next.js (UI layer only)                FastAPI (processing + AI layer)
├── UI: React + Tailwind + shadcn/ui   ├── PDF parsing: pdfplumber
├── Diff view: react-diff-viewer-continued
│                                      ├── Job scraping: httpx → Playwright fallback
└── Session: localStorage              ├── ATS scoring: spaCy + sentence-transformers
                                       ├── AI: Groq Python SDK (provider-swappable)
                                       │   ├── POST /analyze  (SSE stream)
                                       │   ├── POST /clarify  (SSE stream)
                                       │   └── POST /rewrite  (SSE stream)
         │                                        │
         └──────────── REST API ─────────────────┘
```

**Deployment:** Next.js → Vercel · FastAPI → Railway / Fly.io

---

## Frontend (`/frontend`)

| Layer | Library |
|---|---|
| Framework | Next.js (TypeScript, App Router) |
| UI | React + Tailwind CSS + shadcn/ui |
| Diff view | react-diff-viewer-continued |
| File upload | react-dropzone |
| Session state | localStorage (no DB, no auth) |

---

## Server (`/server`)

| Layer | Library |
|---|---|
| Framework | FastAPI + uvicorn |
| Package manager | uv |
| PDF parsing | pdfplumber |
| Job scraping | httpx (primary) → Playwright (fallback) |
| NLP / keywords | spaCy (`en_core_web_sm`) |
| Semantic similarity | sentence-transformers (`all-MiniLM-L6-v2`) |
| AI provider | Groq Python SDK — model `llama-3.3-70b-versatile` (swappable via `GROQ_MODEL` env var) |
| AI streaming | FastAPI `StreamingResponse` (SSE) |
| Schema validation | Pydantic |
| Prompts | Versioned text files in `server/prompts/v1/` |
