from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ScoreRequest(BaseModel):
    resume_text: str
    jd_text: str


def _load_models():
    import spacy
    from sentence_transformers import SentenceTransformer

    nlp = spacy.load("en_core_web_sm")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return nlp, embedder


@router.post("/ats-score")
async def ats_score(body: ScoreRequest):
    if not body.resume_text or not body.jd_text:
        raise HTTPException(status_code=400, detail="Both resume_text and jd_text are required.")

    try:
        import numpy as np
        from sentence_transformers import util

        nlp, embedder = _load_models()

        doc = nlp(body.jd_text)
        raw_keywords = set()
        for chunk in doc.noun_chunks:
            raw_keywords.add(chunk.text.lower().strip())
        for ent in doc.ents:
            raw_keywords.add(ent.text.lower().strip())

        keywords = [kw for kw in raw_keywords if len(kw) > 2]

        resume_lower = body.resume_text.lower()
        matched = [kw for kw in keywords if kw in resume_lower]
        missing = [kw for kw in keywords if kw not in resume_lower]

        jd_emb = embedder.encode(body.jd_text, convert_to_tensor=True)
        resume_emb = embedder.encode(body.resume_text, convert_to_tensor=True)
        similarity = float(util.cos_sim(jd_emb, resume_emb)[0][0])
        score = round(similarity * 100)

        return {
            "score": max(0, min(100, score)),
            "matched_keywords": sorted(matched),
            "missing_keywords": sorted(missing),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")
