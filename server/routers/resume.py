from fastapi import APIRouter, UploadFile, File, HTTPException
import pdfplumber
import io

router = APIRouter()


@router.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    content = await file.read()

    if file.filename and file.filename.endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode text file.")
        return {"text": text, "page_count": 1}

    if file.content_type == "application/pdf" or (
        file.filename and file.filename.endswith(".pdf")
    ):
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n\n".join(pages).strip()
            return {"text": text, "page_count": len(pages)}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parsing failed: {e}")

    raise HTTPException(status_code=400, detail="Unsupported file type. Upload a PDF or .txt file.")
