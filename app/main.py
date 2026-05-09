from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO)

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import shutil

from app.traffic_service import TrafficAnalysisService


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "qinan_simulated_traffic_csv_40nodes"
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(
    title="城市交通网络社区检测及关键路口分析系统",
    version="1.0.0",
    summary="基于模拟城市交通数据的复杂网络分析与可视化平台",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = TrafficAnalysisService(DATA_DIR)

@app.post("/api/import")
async def import_data(
    intersections: UploadFile = File(None),
    road_segments: UploadFile = File(None),
    hourly_traffic: UploadFile = File(None),
    segment_daily: UploadFile = File(None),
):
    """Import dataset CSV files."""
    files = {
        "Intersections.csv": intersections,
        "Road_Segments.csv": road_segments,
        "Hourly_Traffic.csv": hourly_traffic,
        "Segment_Daily.csv": segment_daily,
    }
    
    saved_files = []
    for filename, upload_file in files.items():
        if upload_file:
            target_path = DATA_DIR / filename
            with target_path.open("wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
            saved_files.append(filename)
    
    if saved_files:
        service._load()
        # Clear the lru_cache for _daily_context
        service._daily_context.cache_clear()
        return {"success": True, "message": f"成功导入文件: {', '.join(saved_files)}", "reloaded": True}
    
    return {"success": False, "message": "未收到任何文件"}

@app.post("/api/analyze")
def run_analysis():
    """Explicitly trigger analysis by clearing cache and re-fetching data."""
    service._daily_context.cache_clear()
    # Trigger a run to ensure cache is warm and analysis is done
    service._daily_context(service.default_date)
    return {"success": True, "message": "分析完成"}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"code": 400, "message": "参数错误", "detail": exc.errors()})


@app.exception_handler(Exception)
async def internal_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        raise exc
    return JSONResponse(status_code=500, content={"code": 500, "message": "服务错误", "detail": str(exc)})


@app.get("/api/meta")
def get_meta() -> dict:
    return service.meta()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def get_dashboard(
    date: str | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
) -> dict:
    return service.dashboard(date or service.default_date, hour if hour is not None else service.default_hour)

@app.get("/api/network")
def get_network(
    date: str | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
) -> dict:
    return service.api_network(date or service.default_date, hour if hour is not None else service.default_hour)


@app.get("/api/community")
def get_community(
    date: str | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
) -> dict:
    return service.api_community(date or service.default_date, hour if hour is not None else service.default_hour)


@app.get("/api/key-nodes")
def get_key_nodes(
    date: str | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    return service.api_key_nodes(date or service.default_date, hour if hour is not None else service.default_hour, limit)


@app.get("/api/intersections/{intersection_id}")
def get_intersection_detail(intersection_id: str, date: str | None = Query(default=None)) -> dict:
    try:
        return service.api_intersection_detail(intersection_id, date or service.default_date)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/intersection/{intersection_id}")
def get_intersection_detail_alias(intersection_id: str, date: str | None = Query(default=None)) -> dict:
    return get_intersection_detail(intersection_id, date)


@app.get("/@vite/client")
def vite_client():
    """兼容某些环境下浏览器自动请求 Vite 客户端脚本的问题"""
    return Response(content="", media_type="application/javascript")

@app.get("/")
def index() -> FileResponse:
    if not (STATIC_DIR / "index.html").exists():
        raise HTTPException(status_code=404, detail="Static index.html not found")
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )
