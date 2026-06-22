# role-craft — Implementation Plan (MVP)

## Overview

Greenfield build. Monorepo with `/client` (Next.js — pure UI) and `/server` (FastAPI + uv — all processing + AI). UI is a **single-page wizard** at `/` — state machine steps the user through the full flow.

**MVP scope:** Core wizard flow end-to-end. Text file export only (no PDF). No user accounts. No version history.

**Current state:** `/server` is empty; `/client` does not exist yet.

---

## Implementation Order

Complete phases 1–9 (full server) before starting 10–18 (client). Each phase has a verification step — do not advance until it passes.

---

## Phase 1 — Server Project Init

**Goal:** Working FastAPI app that responds to `GET /health`.

**Commands:**
```bash
cd server
uv init .
uv add fastapi "uvicorn[standard]" python-multipart pdfplumber playwright httpx spacy sentence-transformers groq
```

**Files to create:**

`server/.python-version`
```
3.12
```

`server/main.py`
```python
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import load_prompts, load_models

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_prompts()
    load_models(app)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

`server/.env.example`
```
FRONTEND_URL=
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

`server/Procfile`
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

`server/runtime.txt`
```
python-3.12
```

`server/routers/__init__.py` — empty file

`server/.gitignore`
```
__pycache__/
*.pyc
.env
.venv/
*.egg-info/
dist/
```

**Verify:** `uv run uvicorn main:app --reload` → `curl localhost:8000/health` returns `{"status":"ok"}` with no `DeprecationWarning` in logs

---

## Phase 2 — Resume Parser (`POST /parse-resume`)

**File:** `server/routers/resume.py`

**Pydantic model:**
```python
class ParsedResume(BaseModel):
    text: str
    page_count: int
```

**Logic:**
- Accept `UploadFile` via `multipart/form-data`
- If `.pdf` → `pdfplumber.open(file.file)` → join `page.extract_text()` per page
- If `.txt` → `file.read().decode("utf-8")`
- Raise `HTTPException(400)` for unsupported types or empty extracted text
- Return `ParsedResume(text=..., page_count=...)`

**Router setup:**
```python
router = APIRouter(prefix="/parse-resume", tags=["resume"])

@router.post("", response_model=ParsedResume)
async def parse_resume(file: UploadFile = File(...)):
    ...
```

- `.txt` branch: `contents = await file.read()` (UploadFile.read() is a coroutine)
- `.pdf` branch: pass `file.file` (the underlying sync file object) to `pdfplumber.open()`

**Wire into `main.py`:**
```python
from routers import resume
app.include_router(resume.router)
```

**Verify:** `curl -F "file=@sample.pdf" localhost:8000/parse-resume` returns `{text, page_count}`

---

## Phase 3 — Job Scraper (`POST /scrape-job`)

**File:** `server/routers/job.py`

**Request model:**
```python
class JobRequest(BaseModel):
    url: str | None = None
    text: str | None = None
```

**Router setup:**
```python
router = APIRouter(prefix="/scrape-job", tags=["job"])

@router.post("", response_model=dict)
async def scrape_job(req: JobRequest):
    ...
```

**Logic (in order):**
1. If `text` provided → return `{"text": text}` immediately
2. Try `httpx.get(url, timeout=10, follow_redirects=True)` → extract text with stdlib `html.parser` (`HTMLParser` subclass), not regex — regex breaks on nested tags, CDATA, and encoded entities
3. On failure or JS-rendered page → use `async_playwright()` (endpoint is `async def`):
   ```python
   async with async_playwright() as p:
       browser = await p.chromium.launch()
       page = await browser.new_page()
       await page.goto(url, timeout=15000)
       text = await page.inner_text("body")
       await browser.close()
   ```
4. Both fail → `HTTPException(422, "Could not fetch job. Please paste the text directly.")`

**Post-install step (add to Railway post-deploy):**
```bash
uv run playwright install chromium
```

**Verify:** POST `{"url": "https://example.com"}` returns `{"text": "..."}` or a 422 with a clear message.

---

## Phase 4 — ATS Scorer (`POST /ats-score`)

**File:** `server/routers/score.py`

**Request/response models:**
```python
class ScoreRequest(BaseModel):
    resume_text: str
    jd_text: str

class ScoreResult(BaseModel):
    score: int                    # 0–100
    matched_keywords: list[str]
    missing_keywords: list[str]
```

**Router setup:**
```python
router = APIRouter(prefix="/ats-score", tags=["score"])

@router.post("", response_model=ScoreResult)
async def ats_score(req: ScoreRequest, request: Request):
    nlp = request.app.state.nlp
    embedder = request.app.state.embedder
    result = await run_in_threadpool(compute_score, req.resume_text, req.jd_text, nlp, embedder)
    return result
```

**Scoring (weighted sum) — implement as plain `def compute_score(...)` called via `run_in_threadpool`:**
- **40% keyword match** — spaCy `en_core_web_sm`: extract noun chunks + named entities from JD; check presence in resume (case-insensitive)
- **30% semantic similarity** — `sentence-transformers` `all-MiniLM-L6-v2`: cosine similarity of full-doc embeddings
- **20% experience relevance** — regex match job titles and year patterns in both texts; compute overlap ratio
- **10% formatting heuristics** — regex check for section headers (`SKILLS`, `EXPERIENCE`, `EDUCATION`) in resume

spaCy and sentence-transformers are CPU-bound sync calls. Running them directly in an `async def` endpoint blocks the Uvicorn event loop. Wrapping with `run_in_threadpool` (from `starlette.concurrency`) offloads to a thread — no extra dependency.

**Models are loaded in `lifespan` (see Phase 1), not at module level.** Module-level loading adds cost to every import and every `--reload` cycle.

**Post-install step (add to Railway post-deploy):**
```bash
uv run python -m spacy download en_core_web_sm
```

**Verify:** POST `{resume_text, jd_text}` returns `{score: 72, matched_keywords: [...], missing_keywords: [...]}`

---

## Phase 5 — Prompt Files

**Directory:** `server/prompts/v1/`

Three plain-text files — loaded once at startup, injected as system messages. Changing behavior = edit the file, no code change needed.

**`server/prompts/v1/analyze.txt`** — instruct the model to:
- Compare the JD against the resume
- Return output in three sections: `## MISSING_SKILLS`, `## WEAK_BULLETS`, `## SUMMARY`
- Rate each resume bullet as `[WEAK]`, `[MEDIUM]`, or `[STRONG]`
- List skills from the JD that are absent from the resume

**`server/prompts/v1/clarify.txt`** — instruct the model to:
- Ask one yes/no question per missing skill, one at a time
- Acknowledge the user's answer before moving to the next skill
- Never assume the user has or doesn't have a skill

**`server/prompts/v1/rewrite.txt`** — instruct the model to:
- Rewrite the resume to match the JD using active language and JD terminology
- Incorporate only skills the user explicitly confirmed
- Strengthen weak bullets using JD vocabulary
- Mark unresolved gaps with `[GAP: skill_name]` — never fabricate experience

**Create `server/config.py`** (do not put this in `main.py` — routers must import from here, not from `main`, to avoid circular imports):

```python
from pathlib import Path
from fastapi import FastAPI
import spacy
from sentence_transformers import SentenceTransformer

PROMPTS: dict[str, str] = {}

def load_prompts() -> None:
    for name in ["analyze", "clarify", "rewrite"]:
        PROMPTS[name] = Path(f"prompts/v1/{name}.txt").read_text()

def load_models(app: FastAPI) -> None:
    app.state.nlp = spacy.load("en_core_web_sm")
    app.state.embedder = SentenceTransformer("all-MiniLM-L6-v2")
```

`main.py` calls `load_prompts()` and `load_models(app)` in the `lifespan` handler (see Phase 1). AI routers import `PROMPTS` from `config`, and receive `nlp`/`embedder` via `request.app.state`.

---

## Phase 6 — Groq Client + SSE Helper

**File:** `server/groq_client.py`

```python
import os
from groq import Groq
from fastapi.responses import StreamingResponse

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def stream_groq(messages: list[dict]) -> StreamingResponse:
    def generate():
        with client.chat.completions.stream(model=MODEL, messages=messages) as stream:
            for chunk in stream:
                # choices can be empty on finish-reason chunks — guard to avoid IndexError
                delta = chunk.choices[0].delta.content if chunk.choices else ""
                if delta:
                    yield f"data: {delta}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

All three AI routers import and call `stream_groq(messages)`.

---

## Phase 7 — Gap Analysis (`POST /analyze`)

**File:** `server/routers/analyze.py`

**Request model:**
```python
class AnalyzeRequest(BaseModel):
    jd_text: str
    resume_text: str
    ats_result: dict
```

**Router setup:** `router = APIRouter(prefix="/analyze", tags=["ai"])`

**Logic:**
```python
from config import PROMPTS  # not from main

messages = [
    {"role": "system", "content": PROMPTS["analyze"]},
    {"role": "user", "content": f"JD:\n{jd_text}\n\nRESUME:\n{resume_text}\n\nATS RESULT:\n{ats_result}"},
]
return stream_groq(messages)
```

**Verify:** SSE stream from `POST /analyze` returns markdown with `## MISSING_SKILLS`, `## WEAK_BULLETS`, `## SUMMARY` sections.

---

## Phase 8 — Clarification Chat (`POST /clarify`)

**File:** `server/routers/clarify.py`

**Request model:**
```python
class ClarifyRequest(BaseModel):
    messages: list[dict]       # [{role, content}] conversation so far
    missing_skills: list[str]
```

**Router setup:** `router = APIRouter(prefix="/clarify", tags=["ai"])`

**Logic:**
```python
from config import PROMPTS  # not from main

system = PROMPTS["clarify"] + f"\n\nMissing skills to resolve: {missing_skills}"
full_messages = [{"role": "system", "content": system}] + messages
return stream_groq(full_messages)
```

**Verify:** POST with `messages=[{"role":"user","content":"yes"}]` and a skill list → AI asks about the next skill.

---

## Phase 9 — Resume Rewrite (`POST /rewrite`)

**File:** `server/routers/rewrite.py`

**Request model:**
```python
class RewriteRequest(BaseModel):
    resume_text: str
    jd_text: str
    confirmed_skills: list[str]
    analysis_summary: str
```

**Router setup:** `router = APIRouter(prefix="/rewrite", tags=["ai"])`

**Logic:**
```python
from config import PROMPTS  # not from main

user_content = (
    f"RESUME:\n{resume_text}\n\n"
    f"JD:\n{jd_text}\n\n"
    f"CONFIRMED SKILLS:\n{confirmed_skills}\n\n"
    f"ANALYSIS:\n{analysis_summary}"
)
messages = [
    {"role": "system", "content": PROMPTS["rewrite"]},
    {"role": "user", "content": user_content},
]
return stream_groq(messages)
```

**Verify:** Stream returns full rewritten resume text; skills not confirmed appear as `[GAP: skill_name]`.

---

## Phase 10 — Client Scaffold

**Commands (run from repo root):**
```bash
npx create-next-app@latest client --typescript --tailwind --app --no-src-dir --import-alias "@/*"
cd client
npx shadcn@latest init          # Default style, CSS variables: yes
npx shadcn@latest add card button badge textarea input tabs skeleton
npm install react-diff-viewer-continued react-dropzone
```

**Create:** `client/.env.local.example`
```
NEXT_PUBLIC_SERVER_URL=http://localhost:8000
```

**Verify:** `npm run dev` → `localhost:3000` loads without errors; Tailwind styles apply.

---

## Phase 11 — Types + API Client

**File:** `client/lib/types.ts`
```ts
export type Step = 'job' | 'upload' | 'analysis' | 'review' | 'export'
export type Message = { role: 'user' | 'assistant'; content: string }
export type ParsedResume = { text: string; page_count: number }
export type ScoreResult = {
  score: number
  matched_keywords: string[]
  missing_keywords: string[]
}
export type AppState = {
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

**File:** `client/lib/api.ts`

Typed functions — each throws on non-2xx response:
```ts
const BASE = process.env.NEXT_PUBLIC_SERVER_URL

export async function scrapeJob(payload: { url?: string; text?: string }): Promise<{ text: string }>
export async function parseResume(file: File): Promise<ParsedResume>
export async function atsScore(resumeText: string, jdText: string): Promise<ScoreResult>
export async function* streamAnalyze(payload: AnalyzeRequest): AsyncGenerator<string>
export async function* streamClarify(payload: ClarifyRequest): AsyncGenerator<string>
export async function* streamRewrite(payload: RewriteRequest): AsyncGenerator<string>
```

**Shared SSE helper (used by all three stream functions):**
```ts
async function* streamSSE(url: string, body: object): AsyncGenerator<string> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()!
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]'))
        yield line.slice(6)
    }
  }
}
```

**Verify:** Import in a test component; call `atsScore("...", "...")` → check network tab shows the request.

---

## Phase 12 — Global State (localStorage-synced)

**File:** `client/lib/store.ts`

```ts
import { useState, useEffect } from 'react'
import type { AppState } from './types'

const STORAGE_KEY = 'role-craft-state'
const INITIAL: AppState = {
  jdText: '', resumeText: '',
  atsScoreBefore: 0, atsScoreAfter: 0,
  missingKeywords: [], analysisResult: '',
  clarificationMessages: [], confirmedSkills: [],
  rewrittenResume: '',
}

export function useAppState() {
  const [state, setState] = useState<AppState>(() => {
    if (typeof window === 'undefined') return INITIAL
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : INITIAL
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const resetState = () => {
    localStorage.removeItem(STORAGE_KEY)
    setState(INITIAL)
  }

  return { state, setState, resetState }
}
```

**Verify:** Set a value in state, refresh page → value persists. Call `resetState()` → state and localStorage both clear.

---

## Phase 13 — Wizard Shell + Step Indicator

**File:** `client/app/layout.tsx` — minimal wrapper with Inter font:
```tsx
import { Inter } from 'next/font/google'
const inter = Inter({ subsets: ['latin'] })
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body className={inter.className}>{children}</body></html>
}
```

**File:** `client/components/StepIndicator.tsx`
- Props: `currentStep: Step`
- Renders 5 labeled steps: Job → Upload → Analysis → Review → Export
- Active step: filled circle; completed: checkmark icon; future: muted/gray

**File:** `client/app/page.tsx`
```tsx
'use client'
import { useState } from 'react'
import type { Step } from '@/lib/types'
import { useAppState } from '@/lib/store'
import StepIndicator from '@/components/StepIndicator'
import JobInput from '@/components/steps/JobInput'
import ResumeUpload from '@/components/steps/ResumeUpload'
import GapAnalysis from '@/components/steps/GapAnalysis'
import DiffReview from '@/components/steps/DiffReview'
import Export from '@/components/steps/Export'

export default function Page() {
  const [step, setStep] = useState<Step>('job')
  const { state, setState, resetState } = useAppState()

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <StepIndicator currentStep={step} />
      {step === 'job' && <JobInput state={state} setState={setState} onNext={() => setStep('upload')} />}
      {step === 'upload' && <ResumeUpload state={state} setState={setState} onBack={() => setStep('job')} onNext={() => setStep('analysis')} />}
      {step === 'analysis' && <GapAnalysis state={state} setState={setState} onNext={() => setStep('review')} />}
      {step === 'review' && <DiffReview state={state} setState={setState} onNext={() => setStep('export')} />}
      {step === 'export' && <Export state={state} onReset={() => { resetState(); setStep('job') }} />}
    </main>
  )
}
```

**Verify:** Page renders with step indicator; clicking through steps renders the correct component.

---

## Phase 14 — Step 1: Job Input

**File:** `client/components/steps/JobInput.tsx`

**Props:** `{ state, setState, onNext }`

**UI:**
- shadcn `Tabs` with two tabs: "Paste URL" / "Paste Text"
- URL tab: `Input` + "Fetch Job" `Button` → calls `scrapeJob({ url })` → sets `state.jdText` → populates a read-only `Textarea` showing the result
- Text tab: `Textarea` → sets `state.jdText` on change
- Loading spinner on fetch; error shown as red text below input on failure
- "Next" `Button`: disabled until `state.jdText.length > 100`; on click → `onNext()`

**Verify:** Paste a URL → JD text appears; paste raw text → "Next" button enables at 100+ chars.

---

## Phase 15 — Step 2: Resume Upload

**File:** `client/components/steps/ResumeUpload.tsx`

**Props:** `{ state, setState, onBack, onNext }`

**UI:**
- `useDropzone({ accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'] } })`
- Drop zone: dashed border, upload icon, "Drop PDF or TXT here" label
- On drop → `parseResume(file)` → sets `state.resumeText`
- Preview: first 300 chars of `state.resumeText` in a read-only `Textarea`
- Show `page_count` as a `Badge` if PDF
- Error state: red border + message below drop zone
- "Back" + "Next" buttons; "Next" disabled until `state.resumeText` is set

**Verify:** Drop a PDF → text preview appears with page count badge; "Next" enables.

---

## Phase 16 — Step 3: Gap Analysis + Clarification

**File:** `client/components/steps/GapAnalysis.tsx`

**Props:** `{ state, setState, onNext }`

**On mount, fire in parallel:**
1. `atsScore(state.resumeText, state.jdText)` → sets `state.atsScoreBefore`, `state.missingKeywords`
2. `streamAnalyze({...})` → accumulate chunks into local `analysisText` state; on `[DONE]` → set `state.analysisResult`

**Left panel:**
- ATS score `Badge` (color-coded: <50 red, 50–74 yellow, ≥75 green)
- `state.missingKeywords` as `Badge` chips
- `Skeleton` loader while scoring runs

**Right panel:**
- Streaming analysis text rendered as `<pre className="whitespace-pre-wrap">`
- `Skeleton` placeholder while stream hasn't started

**After analysis completes, if `missingKeywords.length > 0`:**
- Render clarification chat section
- Local `input` state for user message
- User submits → append to `state.clarificationMessages` → `streamClarify({ messages, missing_skills })` → stream AI response → append AI message to state
- "Mark as confirmed" / "Don't have it" buttons to populate `state.confirmedSkills`
- "Generate Rewrite" `Button`: enabled when all missing skills are resolved; calls `onNext()`

**Verify:** On mount, both calls fire; left panel shows score + keyword chips; right panel streams; chat appears and responds.

---

## Phase 17 — Step 4: Diff Review + Edit

**File:** `client/components/steps/DiffReview.tsx`

**Props:** `{ state, setState, onNext }`

**On mount:**
1. `streamRewrite({ resume_text, jd_text, confirmed_skills, analysis_summary })` → accumulate chunks → set `state.rewrittenResume` on `[DONE]`
2. After stream completes → `atsScore(state.rewrittenResume, state.jdText)` → sets `state.atsScoreAfter`

**UI:**
- Score bar: "Before: 62 → After: 84" with colored `Badge` components; `Skeleton` while loading
- `ReactDiffViewer` (from `react-diff-viewer-continued`): `oldValue={state.resumeText}` `newValue={state.rewrittenResume}` `splitView={true}`; shown only after stream completes
- Below diff: editable `Textarea` pre-filled with `state.rewrittenResume`; on change → updates `state.rewrittenResume`
- "Continue to Export" `Button` → `onNext()`

**Verify:** Diff renders with colored additions/deletions; textarea is editable; ATS score shows improvement.

---

## Phase 18 — Step 5: Export

**File:** `client/components/steps/Export.tsx`

**Props:** `{ state, onReset }`

**UI (centered `Card`):**
- Final ATS score `Badge`
- "Download as Text" `Button`:
  ```ts
  const blob = new Blob([state.rewrittenResume], { type: 'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'resume-optimized.txt'
  a.click()
  ```
- "Copy to Clipboard" `Button`: `navigator.clipboard.writeText(state.rewrittenResume)` → show "Copied!" label for 2 seconds
- "Start Over" `Button` → calls `onReset()`

**Verify:** Download produces a `.txt` file with the correct content; clipboard copy works; "Start Over" clears localStorage and resets to step 1.

---

## Phase 19 — Error Handling + Loading States

**Goal:** Each step degrades gracefully on failure.

**Per-step errors:**
- `JobInput` — scrape fails → "Couldn't fetch. Switch to Paste Text tab."
- `ResumeUpload` — parse fails → "Could not extract text. Try a different file."
- `GapAnalysis` — scoring/analysis fails → error banner with "Retry" button
- `DiffReview` — rewrite fails → "Rewrite failed." button to re-trigger stream

**Loading skeletons:**
- Each async section uses shadcn `Skeleton` (or `animate-pulse` div) while the request is in-flight
- SSE streams: show partial text as it arrives — no skeleton needed

**Mobile responsiveness:**
- `GapAnalysis` panels: stack vertically below `md:` breakpoint
- `DiffReview`: hide diff viewer on small screens; show only the editable textarea
- All steps: `px-4` padding, full-width buttons on mobile

---

## Phase 20 — Deployment

**Client (Vercel):**
- Set env var `NEXT_PUBLIC_SERVER_URL` in Vercel dashboard (value: Railway URL)
- Deploy: `vercel --prod` from `/client`

**Server (Railway):**
- Connect repo; set root directory to `/server`
- Post-deploy commands:
  ```bash
  playwright install chromium && python -m spacy download en_core_web_sm
  ```
- Env vars to set: `FRONTEND_URL`, `GROQ_API_KEY`, `GROQ_MODEL`

**CLAUDE.md — fill in Commands section:**
```
## Commands
cd server && uv run uvicorn main:app --reload   # API at :8000
cd client && npm run dev                        # UI at :3000
```

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

---

## Verification (End-to-End)
1. Start both dev servers
2. Step 1: paste a real job URL → confirm JD text appears
3. Step 2: drop a real PDF → confirm text preview and page count
4. Step 3: confirm ATS score appears, analysis streams, clarification chat responds
5. Step 4: confirm diff renders with changes highlighted; ATS score improves
6. Step 5: download `.txt` → file matches textarea content
7. Refresh mid-flow → localStorage restores all state
8. "Start Over" → localStorage cleared, wizard resets to step 1
