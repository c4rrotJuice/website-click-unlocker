from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Template engine
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def render_url(request: Request, url: str = Form(...), unlock: str = Form("on")):
    unlock_bool = unlock == "on"
    return templates.TemplateResponse("home.html", {
        "request": request,
        "url": url,
        "unlock": unlock_bool
    })


from app.routes import render
app.include_router(render.router)

