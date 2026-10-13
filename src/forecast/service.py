# -*- coding: utf-8 -*-
"""Job lifecycle: load seed evidence, run graph in background, persist JSON."""
from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from config.settings import DATA_SEED_DIR, JOBS_DIR

from .graph import run_forecast
from .schemas import TopicEvidence

_LOCK = threading.Lock()


def load_seed_evidence() -> List[TopicEvidence]:
    raw = json.loads((DATA_SEED_DIR / "topics.json").read_text(encoding="utf-8"))
    return [
        TopicEvidence(
            topic_name=item["name"],
            keywords=item.get("keywords", []),
            example=item.get("example", ""),
            ipc_trend=item.get("ipc_trend", ""),
        )
        for item in raw
    ]


def _job_dir(job_id: str) -> Path:
    path = JOBS_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_job() -> Dict:
    job_id = f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0.0,
        "log": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "error": "",
    }
    _job_dir(job_id).joinpath("job.json").write_text(
        json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    threading.Thread(target=_run, args=(job_id,), daemon=True).start()
    return job


def get_job(job_id: str) -> Dict | None:
    path = _job_dir(job_id) / "job.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_result(job_id: str) -> Dict | None:
    path = _job_dir(job_id) / "result.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save(job_id: str, payload: Dict) -> None:
    _job_dir(job_id).joinpath("job.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _run(job_id: str) -> None:
    with _LOCK:
        job = get_job(job_id) or {}
        job.update(status="running", stage="prepare")
        _save(job_id, job)
        try:
            evidence = load_seed_evidence()
            final = run_forecast(evidence, job_id)

            result = _build_result(final)
            _job_dir(job_id).joinpath("result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            job.update(status="completed", stage="done", progress=1.0,
                       log=list(final.get("log", [])))
            _save(job_id, job)
        except Exception as exc:  # noqa: BLE001
            job = get_job(job_id) or {}
            job.update(status="failed", stage="error", error=str(exc),
                       log=[*job.get("log", []), f"失败: {exc}", traceback.format_exc()])
            _save(job_id, job)


def _build_result(final) -> Dict:
    forecasts = [f.model_dump() for f in final.get("forecasts", [])]
    roadmaps = [r.model_dump() for r in final.get("roadmaps", [])]
    critiques = [c.model_dump() for c in final.get("critiques", [])]
    synthesis = final.get("synthesis")
    synthesis = synthesis.model_dump() if synthesis else {}
    confidences = [f["confidence"] for f in forecasts]
    return {
        "job_id": final.get("job_id"),
        "baseline_year": 2025,
        "target_year": 2040,
        "time_nodes": [2030, 2035, 2040],
        "forecasts": forecasts,
        "critiques": critiques,
        "roadmaps": roadmaps,
        "synthesis": synthesis,
        "stats": {
            "topic_count": len(forecasts),
            "avg_confidence": round(sum(confidences) / len(confidences), 1)
            if confidences else 0,
            "revised": final.get("revision_count", 0) > 0,
        },
    }
