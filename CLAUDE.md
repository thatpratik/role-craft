# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**role-craft** is an AI-powered resume optimizer for career switchers. It takes a job description and a resume, identifies ATS gaps, and rewrites the resume to match — without fabricating experience.

## Architecture

Two services:

**`/frontend`** — Next.js app (TypeScript)
- UI: React + Tailwind CSS + shadcn/ui
- AI calls: Vercel AI SDK → Groq (provider-swappable via config)
- Session state: `localStorage` (no auth, no DB)
- Deployment: Vercel

**`/server`** — FastAPI app (Python)
- PDF parsing: `pdfplumber`
- Job scraping: `Playwright` → text paste fallback
- ATS scoring + NLP: `spaCy` + `sentence-transformers`
- Diff generation: `diff-match-patch`
- PDF export: `Playwright` headless
- Deployment: Railway or Fly.io

Frontend calls backend via REST API for all processing. AI rewriting and streaming happen in Next.js API routes using Vercel AI SDK.

## Commands

> To be filled in once project scaffolding is complete.

## Key Decisions
- AI provider is swappable — Groq is default but any Vercel AI SDK-compatible provider works
- No user accounts — session-only, state lives in browser
- AI only rewrites existing content — never fabricates skills or experience
- Missing skills trigger an interactive question to the user before being flagged or added
