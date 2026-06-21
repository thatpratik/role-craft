from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re

router = APIRouter()


class JobRequest(BaseModel):
    url: str | None = None
    text: str | None = None


@router.post("/scrape-job")
async def scrape_job(body: JobRequest):
    if body.text:
        return {"text": body.text.strip()}

    if body.url:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(body.url, timeout=15000)
                raw = await page.inner_text("body")
                await browser.close()

            text = re.sub(r"\n{3,}", "\n\n", raw).strip()
            return {"text": text}
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not scrape the URL ({e}). Please paste the job description text instead.",
            )

    raise HTTPException(status_code=400, detail="Provide either a URL or job description text.")
