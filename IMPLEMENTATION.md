# role-craft — Implementation Plan

## Overview

Greenfield build. Monorepo with `/frontend` (Next.js + Vercel AI SDK → Groq) and `/backend` (FastAPI + uv). UI is a **single-page wizard** at `/` — state machine steps the user through the full flow.

---

## Phase 1 — Project Scaffolding

### 1.1 Backend (`/backend`)
- `uv init backend` → `pyproject.toml`, `.python-version`
- Dependencies: `fastapi`, `uvicorn[standard]`, `pdfplumber`, `playwright`, `spacy`, `sentence-transformers`, `diff-match-patch`, `python-multipart`
- Entry: `backend/main.py` — FastAPI app with CORS, `/health` GET endpoint
- `backend/routers/` — one file per domain: `resume.py`, `job.py`, `score.py`, `diff.py`, `export.py`
- `backend/Procfile` for Railway: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`

### 1.2 Frontend (`/frontend`)
- `npx create-next-app@latest frontend --typescript --tailwind --app`
- `npx shadcn@latest init` — default style, CSS variables
- Install: `ai`, `@ai-sdk/groq`, `react-diff-viewer-continued`, `react-dropzone`
- `frontend/lib/api.ts` — typed fetch wrapper for all backend REST calls
- `frontend/lib/ai.ts` — Groq provider init (model swappable via `GROQ_MODEL` env var)
- `/frontend/.env.local.example` — `GROQ_API_KEY`, `NEXT_PUBLIC_BACKEND_URL`

---

## Phase 2 — Backend Processing Endpoints

### 2.1 Resume Parsing — `POST /parse-resume`
- Accepts: `multipart/form-data` with `file` (PDF or `.txt`)
- Logic: `pdfplumber.open()` → extract text per page → join
- Returns: `{ text: str, page_count: int }`
- File: `backend/routers/resume.py`

### 2.2 Job Scraping — `POST /scrape-job`
- Accepts: `{ url?: str, text?: str }`
- Logic: if URL → Playwright `page.goto(url)` → `page.inner_text("body")` → clean whitespace; if text → pass through
- Fallback: Playwright failure → return error prompting user to paste text
- File: `backend/routers/job.py`

### 2.3 ATS Scoring — `POST /ats-score`
- Accepts: `{ resume_text: str, jd_text: str }`
- Logic:
  - spaCy `en_core_web_sm` → extract noun chunks + entities from JD as required keywords
  - Check which keywords appear in resume (case-insensitive)
  - sentence-transformers `all-MiniLM-L6-v2` → cosine similarity of embeddings → 0–100 score
- Returns: `{ score: int, missing_keywords: list[str], matched_keywords: list[str] }`
- File: `backend/routers/score.py`

### 2.4 Diff Generation — `POST /diff`
- Accepts: `{ original: str, rewritten: str }`
- Logic: `diff_match_patch` → return unified diff patches
- Returns: `{ patches: list, html_diff: str }`
- File: `backend/routers/diff.py`

### 2.5 PDF Export — `POST /export-pdf`
- Accepts: `{ html: str }` — pre-rendered resume HTML
- Logic: Playwright `page.set_content(html)` → `page.pdf()` → stream bytes
- Returns: `application/pdf` binary response
- File: `backend/routers/export.py`

---

## Phase 3 — AI Layer (Next.js API Routes)

All routes in `frontend/app/api/`. Use Vercel AI SDK `streamText` with Groq. Model default: `llama-3.3-70b-versatile`.

### 3.1 Gap Analysis — `POST /api/analyze`
- Input: `{ jd_text, resume_text, ats_result }`
- Prompt: analyze JD vs resume → identify weak bullets (rated weak/medium/strong), skill gaps, missing keywords, tone mismatches
- Returns: streaming markdown (sections: `MISSING_SKILLS`, `WEAK_BULLETS`, `SUMMARY`)

### 3.2 Interactive Clarification — `POST /api/clarify`
- Input: `{ messages: Message[], missing_skills: string[] }` (chat history)
- Prompt: for each missing skill not yet resolved, ask user — "Do you have experience with X? It's not in your resume."
- Returns: streaming conversational response; accumulates `confirmed_skills[]`

### 3.3 Resume Rewrite — `POST /api/rewrite`
- Input: `{ resume_text, jd_text, confirmed_skills[], analysis_summary }`
- Prompt constraints:
  - Incorporate confirmed skills naturally
  - Strengthen weak bullets using JD language
  - Never fabricate — only reframe/strengthen existing content
  - Flag (do not fill) gaps user confirmed they don't have
- Returns: streaming rewritten resume text

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
- shadcn components: `Card`, `Button`, `Badge`, `Textarea`, `Input` throughout

### 4.2 Step 1: Job Input (`components/steps/JobInput.tsx`)
- Tab switcher: "Paste URL" / "Paste Text"
- URL tab: text input + "Fetch Job" button → calls backend `/scrape-job` → populates textarea
- Text tab: textarea for direct paste
- "Next" enabled when `jdText.length > 100`

### 4.3 Step 2: Resume Upload (`components/steps/ResumeUpload.tsx`)
- `react-dropzone` — accepts `.pdf`, `.txt`
- On drop → `FormData` → `POST /parse-resume` → sets `resumeText`
- Preview: first 300 chars of extracted text in read-only textarea
- "Next" enabled when `resumeText` is set

### 4.4 Step 3: Gap Analysis + Clarification (`components/steps/GapAnalysis.tsx`)
- On mount: parallel calls — `POST /ats-score` + stream `POST /api/analyze`
- Left panel: ATS score badge (before), missing keywords list, bullet strength breakdown
- Right panel: streaming analysis text
- After analysis complete: if missing keywords → show clarification chat
  - `useChat` hook → `/api/clarify`
  - AI asks about each missing skill one at a time; user replies yes/no
  - "Done" button appears when all skills resolved
- "Generate Rewrite" → advances to step 4

### 4.5 Step 4: Diff Review + Edit (`components/steps/DiffReview.tsx`)
- On mount: stream `/api/rewrite` → once complete, call `/diff` for patches
- Top bar: ATS score before → after (animated counter)
- `react-diff-viewer-continued` — side-by-side old vs new
- Below diff: editable `<textarea>` pre-filled with rewritten resume
- "Approve & Continue" → advances to step 5

### 4.6 Step 5: Export (`components/steps/Export.tsx`)
- "Download PDF" → sends final resume wrapped in HTML template to `POST /export-pdf` → blob download
- "Download Text" → `Blob` + anchor click
- "Start Over" → clears `localStorage`, resets state to step 1

---

## Phase 5 — Integration & Polish

- Wire `frontend/lib/api.ts` with typed functions for every backend endpoint
- Error boundaries on each step (network errors, parse failures, AI refusals)
- Loading skeletons during async operations
- Mobile-responsive layout (Tailwind responsive classes)
- Fill in `CLAUDE.md` Commands section with dev start commands

---

## Phase 6 — Deployment

### 6.1 Vercel (Frontend)
- Env vars: `GROQ_API_KEY`, `NEXT_PUBLIC_BACKEND_URL` (set to Railway URL)
- Deploy: `vercel --prod` from `/frontend`

### 6.2 Railway (Backend)
- `backend/Procfile` + `backend/runtime.txt` (`python-3.12`)
- Post-deploy commands: `playwright install chromium`, `python -m spacy download en_core_web_sm`
- Env vars: `FRONTEND_URL` (for CORS allow-origin)

---

## Verification (End-to-End Test)
1. Run both dev servers: `cd backend && uv run uvicorn main:app --reload` + `cd frontend && npm run dev`
2. Paste a real job URL → confirm scrape returns JD text
3. Upload a real PDF resume → confirm text extraction
4. Complete full wizard: analysis → clarification → rewrite → diff view → PDF download
5. Check ATS score changes between before/after
6. Verify no fabricated content in the rewrite (compare against original resume)
