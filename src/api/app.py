# -*- coding: utf-8 -*-
"""Single-path FastAPI entry for the 2040 construction-technology forecast system."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.forecast import service

app = FastAPI(title="智能建造 2040 技术预测系统", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "forecast-2040", "paradigm": "think-and-execute"}


@app.get("/api/topics")
def topics() -> dict:
    evidence = service.load_seed_evidence()
    return {
        "items": [e.model_dump() for e in evidence],
        "total": len(evidence),
    }


@app.post("/api/forecast", status_code=202)
def start_forecast() -> dict:
    return service.create_job()


@app.get("/api/forecast/{job_id}")
def job_status(job_id: str) -> dict:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="预测任务不存在")
    return job


@app.get("/api/forecast/{job_id}/result")
def job_result(job_id: str) -> dict:
    result = service.get_result(job_id)
    if not result:
        raise HTTPException(status_code=409, detail="结果尚未生成")
    return result
