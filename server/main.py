from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from routers import resume, job, score

app = FastAPI(title="role-craft API")

allowed_origins = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router)
app.include_router(job.router)
app.include_router(score.router)


@app.get("/health")
def health():
    return {"status": "ok"}
