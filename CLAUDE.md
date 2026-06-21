# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**role-craft** is an AI-powered resume optimizer for career switchers. It takes a job description and a resume, identifies ATS gaps, and rewrites the resume to match — without fabricating experience.

## Architecture

Two services:

**`/frontend`** — Next.js app (TypeScript)
- UI: React + Tailwind CSS + shadcn/ui
- Diff view: `react-diff-viewer-continued` (client-side, no server round-trip)
- Session state: `localStorage` (no auth, no DB)
- Deployment: Vercel

**`/server`** — FastAPI app (Python)
- PDF parsing: `pdfplumber`
- Job scraping: `requests` → Playwright fallback → text paste fallback
- ATS scoring + NLP: `spaCy` + `sentence-transformers`
- AI orchestration: Groq Python SDK + SSE streaming (`/analyze`, `/clarify`, `/rewrite`)
- Deployment: Railway or Fly.io

Frontend calls server via REST API for all processing. AI streaming happens in FastAPI using the Groq Python SDK via `StreamingResponse`.

## Commands

> To be filled in once project scaffolding is complete.

## Key Decisions
- All AI orchestration lives in FastAPI — Next.js is a pure UI layer with no API routes
- AI provider is swappable — Groq is default; swap by changing the model/client in `server/routers/`
- No user accounts — session-only, state lives in browser
- AI only rewrites existing content — never fabricates skills or experience
- Missing skills trigger an interactive question to the user before being flagged or added
- Diff is computed client-side — no backend round-trip needed
- PDF export is deferred to post-MVP — text file download for now
