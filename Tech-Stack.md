## Tech Stack

### Architecture
Hybrid — Next.js handles UI and AI calls, FastAPI handles heavy processing. Two services, cleanly separated.

```
Next.js (frontend + AI layer)          FastAPI (processing layer)
├── UI: React + Tailwind + shadcn/ui   ├── PDF parsing: pdfplumber
├── AI: Vercel AI SDK                  ├── Job scraping: Playwright → text fallback
│   └── Provider: Groq (swappable)     ├── ATS scoring: spaCy + sentence-transformers
├── Diff view: react-diff-viewer       ├── Diff engine: diff-match-patch
└── Session: localStorage              └── PDF export: Playwright headless
         │                                        │
         └──────────── REST API ─────────────────┘

Deployment: Vercel (Next.js) + Railway or Fly.io (FastAPI)
```

### Why this split
- Vercel AI SDK is TypeScript-only → lives in Next.js API routes
- PDF parsing, NLP scoring, and scraping are better served by Python libraries
- Provider flexibility: swap Groq for any other model by changing one config value
