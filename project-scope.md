## Problem Statement
Job searching requires constantly tailoring resumes to each job opening to pass ATS (Applicant Tracking System) scans. Doing this manually is time-consuming and repetitive.

## Solution
An AI-powered web app that analyzes a job description and a user's resume, identifies gaps, and automatically rewrites the resume to be ATS-optimized for that specific role.

## Decisions

| Aspect | Decision |
|---|---|
| Platform | Web app |
| Auth | None — session only (no user accounts) |
| Job input | URL (scrape) → fallback to manual text paste |
| Resume input | PDF or text file upload |
| AI behavior | Rewrites resume sections to close ATS gaps |
| Review | Editable final version of the rewritten resume |
| Output | Download as PDF or text file |

## Features
1. **Job input** — paste a job URL (scraped automatically) or paste the job description text directly
2. **Resume input** — upload resume as PDF or text file
3. **Gap analysis** — AI identifies missing keywords, skills, and experience gaps vs. the job description
4. **AI rewrite** — AI rewrites the resume to fill those gaps and optimize for ATS
5. **Review & edit** — user sees the final rewritten resume and can edit any section before downloading
6. **Export** — download the final resume as a PDF or text file
