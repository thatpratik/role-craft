# role-craft — Implementation Plan (MVP)

## Overview

Greenfield build. Monorepo with `/frontend` (Next.js — pure UI) and `/server` (FastAPI + uv — all processing + AI). UI is a **single-page wizard** at `/` — state machine steps the user through the full flow.

**MVP scope:** Core wizard flow end-to-end. Text file export only (no PDF). No user accounts. No version history.

---

## Phase 1 — Project Scaffolding

### 1.1 Server (`/server`)
- `uv init server` → `pyproject.toml`, `.python-version`
- Dependencies: `fastapi`, `uvicorn[standard]`, `pdfplumber`, `playwright`, `httpx`, `spacy`, `sentence-transformers`, `python-multipart`, `groq`
- Entry: `server/main.py` — FastAPI app with CORS, `/health` GET endpoint
- `server/routers/` — `resume.py`, `job.py`, `score.py`, `analyze.py`, `clarify.py`, `rewrite.py`
- `server/Procfile` for Railway: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- `server/.env.example` — `FRONTEND_URL`, `GROQ_API_KEY`, `GROQ_MODEL` (default: `llama-3.3-70b-versatile`)

### 1.2 Frontend (`/frontend`)
- `npx create-next-app@latest frontend --typescript --tailwind --app`
- `npx shadcn@latest init` — default style, CSS variables
- Install: `react-diff-viewer-continued`, `react-dropzone`
- `frontend/lib/api.ts` — typed fetch wrapper for all server REST calls (including SSE streams)
- `frontend/.env.local.example` — `NEXT_PUBLIC_SERVER_URL` (points to Railway URL in prod, `http://localhost:8000` in dev)

---

## Phase 2 — Server Processing Endpoints

### 2.1 Resume Parsing — `POST /parse-resume`
- Accepts: `multipart/form-data` with `file` (PDF or `.txt`)
- Logic: `pdfplumber.open()` → extract text per page → join
- Validate output with Pydantic: `class ParsedResume(BaseModel): text: str; page_count: int`
- Returns: `{ text: str, page_count: int }`
- File: `server/routers/resume.py`

### 2.2 Job Scraping — `POST /scrape-job`
- Accepts: `{ url?: str, text?: str }`
- Logic:
  1. If text → pass through
  2. If URL → try `httpx.get(url)` + extract visible text (fast, no browser)
  3. Fallback → Playwright `page.goto(url)` → `page.inner_text("body")` (JS-rendered pages)
  4. Both fail → return error prompting user to paste text
- Returns: `{ text: str }`
- File: `server/routers/job.py`

### 2.3 ATS Scoring — `POST /ats-score`
- Accepts: `{ resume_text: str, jd_text: str }`
- Logic (weighted):
  - 40% keyword match — spaCy `en_core_web_sm` noun chunks + entities from JD vs resume
  - 30% semantic similarity — sentence-transformers `all-MiniLM-L6-v2` cosine similarity
  - 20% experience relevance — overlap of job titles / years mentioned
  - 10% formatting heuristics — presence of sections (skills, experience, education)
- Returns: `{ score: int, missing_keywords: list[str], matched_keywords: list[str] }`
- File: `server/routers/score.py`

---

## Phase 3 — AI Layer (FastAPI SSE Endpoints)

All AI routes live in `server/routers/`. Use Groq Python SDK with `StreamingResponse` (`text/event-stream`). Model configurable via `GROQ_MODEL` env var.

All prompts stored as versioned text files in `server/prompts/v1/` (e.g., `analyze.txt`, `clarify.txt`, `rewrite.txt`). Loaded at startup and injected into system messages. Changing model behavior = edit the file, no code change needed.

### 3.1 Gap Analysis — `POST /analyze`
- Input: `{ jd_text: str, resume_text: str, ats_result: dict }`
- Prompt: analyze JD vs resume → identify weak bullets (weak/medium/strong), skill gaps, missing keywords
- Returns: SSE stream of markdown text (sections: `MISSING_SKILLS`, `WEAK_BULLETS`, `SUMMARY`)
- File: `server/routers/analyze.py`

### 3.2 Interactive Clarification — `POST /clarify`
- Input: `{ messages: list[dict], missing_skills: list[str] }`
- Prompt: for each unresolved missing skill, ask — "Do you have experience with X? It's not in your resume."
- Returns: SSE stream of conversational response
- File: `server/routers/clarify.py`

### 3.3 Resume Rewrite — `POST /rewrite`
- Input: `{ resume_text: str, jd_text: str, confirmed_skills: list[str], analysis_summary: str }`
- Prompt constraints:
  - Incorporate confirmed skills naturally
  - Strengthen weak bullets using JD language
  - Never fabricate — only reframe/strengthen existing content
  - Flag (do not fill) gaps user confirmed they don't have
- Returns: SSE stream of rewritten resume text
- File: `server/routers/rewrite.py`

---

## Phase 4 — Frontend Wizard UI

Single page at `frontend/app/page.tsx`. Step state: `'job' | 'upload' | 'analysis' | 'review' | 'export'`.

**Global state** (React state + synced to `localStorage`):
```ts
{
  jdText: string
  resumeText: string
  atsScoreBefore: number
  atsScoreAfter: number
  missingKeywords: string[]
  analysisResult: string
  clarificationMessages: Message[]
  confirmedSkills: string[]
  rewrittenResume: string
}
```

### 4.1 App Shell
- `frontend/app/page.tsx` — wizard container with step routing
- `frontend/components/StepIndicator.tsx` — progress bar (steps 1–5)
- shadcn components: `Card`, `Button`, `Badge`, `Textarea`, `Input`

### 4.2 Step 1: Job Input (`components/steps/JobInput.tsx`)
- Tab switcher: "Paste URL" / "Paste Text"
- URL tab: text input + "Fetch Job" button → `POST /scrape-job` → populates textarea
- Text tab: textarea for direct paste
- "Next" enabled when `jdText.length > 100`

### 4.3 Step 2: Resume Upload (`components/steps/ResumeUpload.tsx`)
- `react-dropzone` — accepts `.pdf`, `.txt`
- On drop → `FormData` → `POST /parse-resume` → sets `resumeText`
- Preview: first 300 chars of extracted text in read-only textarea
- "Next" enabled when `resumeText` is set

### 4.4 Step 3: Gap Analysis + Clarification (`components/steps/GapAnalysis.tsx`)
- On mount: parallel calls — `POST /ats-score` + SSE stream `POST /analyze`
- Left panel: ATS score badge (before), missing keywords list, bullet strength notes
- Right panel: streaming analysis text
- After analysis complete: if missing keywords → show clarification chat
  - Manual SSE + message history state → `POST /clarify`
  - AI asks about each missing skill; user replies yes/no
  - "Done" button appears when all skills resolved
- "Generate Rewrite" → advances to step 4

### 4.5 Step 4: Diff Review + Edit (`components/steps/DiffReview.tsx`)
- On mount: SSE stream `POST /rewrite` → accumulate full text
- Once complete: run client-side diff with `react-diff-viewer-continued`
- Top bar: re-call `POST /ats-score` with rewritten text → show score before → after
- Side-by-side diff view (original vs rewritten)
- Below diff: editable `<textarea>` pre-filled with rewritten resume
- "Continue to Export" → advances to step 5

### 4.6 Step 5: Export (`components/steps/Export.tsx`)
- "Download as Text" → `Blob(['...'], {type: 'text/plain'})` + anchor click
- "Copy to Clipboard" → `navigator.clipboard.writeText(rewrittenResume)`
- "Start Over" → clears `localStorage`, resets to step 1

---

## Phase 5 — Integration & Polish

- `frontend/lib/api.ts` — typed functions for every server endpoint + SSE stream helpers
- Error handling per step (network errors, parse failures, AI refusals)
- Loading skeletons during async operations
- Mobile-responsive layout (Tailwind responsive classes)
- Fill in `CLAUDE.md` Commands section with dev start commands

---

## Phase 6 — Deployment

### 6.1 Vercel (Frontend)
- Env vars: `NEXT_PUBLIC_SERVER_URL` (Railway URL)
- No AI keys needed — frontend has no AI calls
- Deploy: `vercel --prod` from `/frontend`

### 6.2 Railway (Server)
- `server/Procfile` + `server/runtime.txt` (`python-3.12`)
- Post-deploy: `playwright install chromium`, `python -m spacy download en_core_web_sm`
- Env vars: `FRONTEND_URL` (CORS), `GROQ_API_KEY`, `GROQ_MODEL`

---

## Post-MVP Backlog
- PDF export (WeasyPrint on server)
- User accounts + saved resumes (PostgreSQL + auth)
- Job application tracker
- Async job queue (pgboss) for heavy processing
- Skill normalization layer (synonym dictionary + embeddings)
- Observability — structured logging + pipeline tracing (OpenTelemetry)
- Caching layer for embeddings and parsed resumes
- Skill graph visualization
- Recruiter lens / "why this change matters" annotations

---

## Verification (End-to-End Test)
1. Run both dev servers: `cd server && uv run uvicorn main:app --reload` + `cd frontend && npm run dev`
2. Paste a real job URL → confirm scrape returns JD text
3. Upload a real PDF resume → confirm text extraction
4. Complete full wizard: analysis → clarification → rewrite → diff view → text download
5. Verify ATS score improves between before/after
6. Verify no fabricated content in the rewrite (compare against original)
