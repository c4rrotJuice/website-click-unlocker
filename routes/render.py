from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from app.services.unprotector import fetch_and_clean_page, run_ocr_on_url

router = APIRouter()

@router.get("/view", response_class=HTMLResponse)
async def view_clean_page(request: Request, url: str, unlock: bool = Query(True)):
    try:
        cleaned_html = await fetch_and_clean_page(url, unlock=unlock)
        return HTMLResponse(content=cleaned_html)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {e}</h1>", status_code=500)

@router.get("/ocr", response_class=HTMLResponse)
async def ocr_page(request: Request, url: str):
    try:
        extracted_text = await run_ocr_on_url(url)
        return HTMLResponse(content=extracted_text)
    except Exception as e:
        return HTMLResponse(content=f"<h1>OCR Error: {e}</h1>", status_code=500)
