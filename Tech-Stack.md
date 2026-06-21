# AI Resume Optimizer – Architecture Review & Improvements

## Overview

This document reviews the current system design for the AI-powered resume optimization platform and outlines key gaps, improvements, and production-grade enhancements.

---

## Current Architecture

### Tech Stack

**Architecture:** Hybrid (Next.js + FastAPI)

```
Next.js (UI layer only)                FastAPI (processing + AI layer)
├── UI: React + Tailwind + shadcn/ui   ├── PDF parsing: pdfplumber
├── Diff view: react-diff-viewer-continued
│                                      ├── Job scraping: requests → Playwright fallback
└── Session: localStorage              ├── ATS scoring: spaCy + sentence-transformers
                                       ├── AI: Groq Python SDK (provider-swappable)
                                       │   ├── POST /analyze  (SSE stream)
                                       │   ├── POST /clarify  (SSE stream)
                                       │   └── POST /rewrite  (SSE stream)
         │                                        │
         └──────────── REST API ─────────────────┘
```

> **MVP scope:** All AI orchestration lives in FastAPI. Next.js is a pure UI layer with no API routes. Diff is computed client-side. PDF export is deferred to post-MVP.

**Deployment:**

* Next.js → Vercel
* FastAPI → Railway / Fly.io

---

## Key Gaps & Improvements

### 1. AI Layer Placement

**Decision:** AI orchestration lives entirely in FastAPI using the Groq Python SDK and `StreamingResponse` (SSE). Next.js is a pure UI layer — no API routes. This centralizes all processing logic in one service and keeps the frontend thin.

---

### 2. No Asynchronous Processing

**Problem:**

* Blocking operations (PDF parsing, scraping, embeddings, LLM calls)

**Solution:**

* Introduce job queue using **pgboss (Postgres-backed)**

**Flow:**

```
User Request → Job Queue → Worker → Store Result → UI Polls
```

**Why pgboss:**

* No Redis required
* Works well with Postgres
* Simple setup for MVP+

---

### 3. No Persistent Storage

**Problem:**

* Session-only (localStorage)
* No history, analytics, or debugging capability

**Solution:**

* Add PostgreSQL (Neon / Supabase)

**Schema Example:**

```ts
Job {
  id: string;
  resume_json: object;
  job_description_json: object;
  ats_score_before: number;
  ats_score_after: number;
  created_at: Date;
}
```

---

### 4. ATS Scoring Needs Structure

**Problem:**

* Current scoring lacks transparency and weighting

**Improvement:**

```
ATS Score =
  40% Keyword match
  30% Semantic similarity
  20% Experience relevance
  10% Formatting heuristics
```

**Benefits:**

* Explainable scoring
* Easier debugging
* Better UX

---

### 5. Resume Schema Normalization

**Problem:**

* PDF parsing produces inconsistent structure

**Solution:**

* Introduce strict schema validation (Pydantic)

```python
class Resume(BaseModel):
    summary: str
    skills: List[str]
    experience: List[Experience]
```

**Enhancement:**

* Use LLM to repair malformed structures

---

### 6. Prompt Engineering Strategy

**Problem:**

* Prompts are not versioned or modular

**Solution:**

* Store prompts as versioned files

```
/prompts/v1/rewrite_experience.txt
/prompts/v1/rewrite_summary.txt
```

**Example Prompt:**

```
Task: Rewrite ONLY the experience bullets
Constraints:
- Do not add new companies
- Do not invent skills
- Add measurable impact where possible
```

---

### 7. Diff Engine

**Decision:** Diff is computed client-side using `react-diff-viewer-continued`. The frontend already has both the original resume text and the rewritten text, so a backend round-trip adds latency with no benefit. Post-MVP, if structured diffs are needed for storage or analytics, move to backend.

---

### 8. Job Scraping Optimization

**Problem:**

* Playwright is heavy and slow

**Improvement Strategy:**

1. Use `requests + readability` first
2. Fallback to Playwright only if needed
3. Cache results

---

### 9. PDF Export

**Decision (MVP):** Deferred. MVP exports resume as a plain text file download (client-side `Blob`). No server round-trip needed.

**Post-MVP:** If pixel-perfect PDF output is required, evaluate WeasyPrint (lighter than Playwright) or pdfkit before defaulting to Playwright headless.

---

## Advanced Improvements

### 1. Skill Normalization Layer

**Goal:**

* Normalize variations in skill naming

**Examples:**

* "Node.js" = "Node"
* "REST API" = "RESTful services"

**Approach:**

* Synonym dictionary + embeddings

---

### 2. Bullet Strength Analyzer

**Before Rewrite:**

* Classify bullets: Weak / Medium / Strong

**After Rewrite:**

* Ensure:

  * Action verb
  * Metrics
  * Impact

---

### 3. Hallucination Guardrails

**Problem:**

* AI may invent skills or experience

**Solution:**

```python
if generated_skill not in original_resume:
    flag_warning()
```

**UX Enhancement:**

* Show warnings:

  * “This skill was inferred, not explicitly found”

---

### 4. Observability

**Add:**

* Structured logging
* Pipeline tracing

**Optional Tools:**

* OpenTelemetry

---

### 5. Caching Layer

**Cache:**

* Embeddings
* Parsed resumes
* Job descriptions

**Benefits:**

* Faster responses
* Reduced cost

---

## Improved Architecture

```
Next.js (UI Layer)
  └── API calls → FastAPI

FastAPI
  ├── API Layer
  ├── Orchestrator (AI pipeline)
  ├── Queue (pgboss)
  ├── Workers
  │     ├── Resume Parser
  │     ├── Job Parser
  │     ├── ATS Analyzer
  │     ├── AI Rewriter
  │     └── Diff Generator
  ├── Cache Layer
  └── Database (PostgreSQL)
```

---

## Strengths of Current Design

* Strong separation of concerns (Next.js vs FastAPI)
* Correct use of Python for NLP tasks
* Use of sentence-transformers for semantic matching
* Diff viewer for improved UX
* Provider abstraction for AI models
* Clean and scalable foundation

---

## Final Verdict

**Current State:**

* Strong architecture
* Good technology choices
* Missing production-level depth

**After Improvements:**

* Production-ready system
* Strong portfolio project
* Suitable for senior-level interviews
* Potential startup-grade foundation

---
