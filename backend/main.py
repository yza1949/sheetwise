"""FastAPI 入口：读配置、允许跨域、把路由挂上。"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(Path(__file__).resolve().parent / ".env")

from auth import allowed_origins
from database import init_db
from routers import ai_routes, auth_routes, datasets, templates

init_db()
app = FastAPI(title="Sheetwise API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_routes.router)
app.include_router(datasets.router)
app.include_router(templates.router)
app.include_router(ai_routes.router)


@app.get("/api/health")
def health():
    return {"ok": True}
