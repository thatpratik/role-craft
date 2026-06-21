## Problem Statement
Job searching requires constantly tailoring resumes to each job opening to pass ATS (Applicant Tracking System) scans. Doing this manually is time-consuming and repetitive.

## Solution
An AI-powered web app that analyzes a job description and a user's resume, identifies gaps, and automatically rewrites the resume to be ATS-optimized for that specific role — without fabricating experience.

## Target User
**Career switchers** — people moving to a new industry or domain who need help reframing their existing experience to match a new role's language and requirements.

## Decisions

| Aspect | Decision |
|---|---|
| Platform | Web app |
| Auth | None — session only (no user accounts) |
| Job input | URL (scrape) → fallback to manual text paste |
| Resume input | PDF or text file upload |
| AI behavior | Rewrites and strengthens existing content only — never fabricates skills or experience |
| Gap handling | If a required skill is missing, AI asks the user if they have it (they may have forgotten to add it) before deciding to flag or fill |
| Review | Diff view (old vs. rewritten) + editable final version |
| Output | Download as PDF or text file |

## Trust & Honesty Guardrails
- AI only rewrites what already exists in the resume
- AI does **not** add skills or experience the user hasn't mentioned
- If the job requires a skill not in the resume, AI **asks the user** — "Do you have experience with X? It's not in your resume." — so forgotten skills can be added legitimately
- Unfillable gaps are flagged clearly so the user knows what's missing

## Features

### Core Flow
1. **Job input** — paste a job URL (scraped automatically) or paste the job description text directly
2. **Resume input** — upload resume as PDF or text file
3. **Gap analysis** — AI identifies missing keywords, weak bullets, and skill gaps vs. the job description
4. **Interactive gap resolution** — for missing skills, AI asks the user whether they have that skill before deciding to flag or incorporate it
5. **AI rewrite** — AI rewrites and strengthens existing resume sections to close gaps and optimize for ATS
6. **Review** — diff view showing exactly what changed (old vs. new), then editable final version
7. **Export** — download the final resume as PDF or text file

### Standout MVP Features
- **ATS score before/after** — match score (e.g. 62 → 87) showing the improvement
- **Missing keywords highlighted** — visual list of JD keywords absent from the resume
- **Diff view of changes** — Git-style comparison of original vs. rewritten content
- **Bullet strength rating** — each resume bullet rated weak/medium/strong with reasoning

## Out of Scope (for MVP)
- User accounts and saved resumes
- Version history / job tracking
- Skill graph visualization
- Recruiter lens / "why this change matters" annotations
