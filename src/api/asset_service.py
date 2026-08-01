# -*- coding:utf-8 -*-
import hashlib
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.report.roadmap_charts import generate_all_charts, generate_all_topics_comparison

ASSET_TITLES = {
    "combined": "综合分析图",
    "timeline": "时间轴路线图",
    "radar": "技术能力雷达图",
    "comparison": "跨主题综合比较图",
}


def stable_topic_id(topic_name: str) -> str:
    digest = hashlib.sha256(topic_name.encode("utf-8")).hexdigest()[:10]
    return f"topic_{digest}"


def _asset_id(topic_id: Optional[str], kind: str, filename: str) -> str:
    material = f"{topic_id or 'global'}:{kind}:{filename}"
    return f"asset_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _is_within(path: Path, directory: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(directory.resolve())]) == str(directory.resolve())
    except ValueError:
        return False


def _to_asset_record(
    job_id: str,
    assets_dir: Path,
    path: Path,
    topic_id: Optional[str],
    topic_name: Optional[str],
    kind: str,
) -> Optional[Dict[str, Any]]:
    if not path.exists() or not _is_within(path, assets_dir):
        return None
    relative_path = path.resolve().relative_to(assets_dir.resolve()).as_posix()
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    asset_id = _asset_id(topic_id, kind, relative_path)
    base_url = f"/api/forecast/jobs/{job_id}/assets/{asset_id}"
    return {
        "asset_id": asset_id,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "kind": kind,
        "title": ASSET_TITLES.get(kind, kind),
        "media_type": media_type,
        "filename": path.name,
        "relative_path": relative_path,
        "url": base_url,
        "download_url": f"{base_url}?download=true",
    }


def generate_job_assets(
    job_id: str,
    job_dir: Path,
    roadmaps: Iterable[Dict[str, Any]],
    topic_ids_by_name: Dict[str, str],
) -> Dict[str, Any]:
    """Generate PNG assets for a job and return an API-safe index."""
    assets_dir = job_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []
    roadmaps = list(roadmaps)

    for roadmap in roadmaps:
        topic_name = str(roadmap.get("topic_name") or "未命名主题")
        topic_id = topic_ids_by_name.get(topic_name, stable_topic_id(topic_name))
        topic_dir = assets_dir / topic_id
        try:
            chart_paths = generate_all_charts(roadmap, str(topic_dir))
        except Exception as exc:  # pragma: no cover - defensive integration boundary
            failures.append({"topic_name": topic_name, "kind": "all", "error": str(exc)})
            continue
        for kind in ("combined", "timeline", "radar"):
            path_value = chart_paths.get(kind)
            record = _to_asset_record(
                job_id, assets_dir, Path(path_value) if path_value else Path(),
                topic_id, topic_name, kind
            )
            if record:
                records.append(record)
            else:
                failures.append({"topic_name": topic_name, "kind": kind, "error": "图表未生成"})

    if roadmaps:
        comparison_path = assets_dir / "all-topics-comparison.png"
        try:
            generated = generate_all_topics_comparison(roadmaps, str(comparison_path))
            record = _to_asset_record(
                job_id, assets_dir, Path(generated) if generated else comparison_path,
                None, None, "comparison"
            )
            if record:
                records.append(record)
            else:
                failures.append({"topic_name": "全主题", "kind": "comparison", "error": "图表未生成"})
        except Exception as exc:  # pragma: no cover - plotting boundary
            failures.append({"topic_name": "全主题", "kind": "comparison", "error": str(exc)})

    return {
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets": records,
        "failed_assets": failures,
    }


def find_asset(asset_index: Dict[str, Any], asset_id: str) -> Optional[Dict[str, Any]]:
    return next((asset for asset in asset_index.get("assets", []) if asset.get("asset_id") == asset_id), None)


def resolve_asset_file(job_dir: Path, asset: Dict[str, Any]) -> Optional[Path]:
    assets_dir = (job_dir / "assets").resolve()
    relative_path = asset.get("relative_path")
    if not isinstance(relative_path, str):
        return None
    candidate = (assets_dir / relative_path).resolve()
    if not _is_within(candidate, assets_dir) or not candidate.is_file():
        return None
    return candidate


def filter_assets(
    asset_index: Dict[str, Any], topic_id: Optional[str] = None, kind: Optional[str] = None
) -> List[Dict[str, Any]]:
    return [
        asset for asset in asset_index.get("assets", [])
        if (topic_id is None or asset.get("topic_id") == topic_id)
        and (kind is None or asset.get("kind") == kind)
    ]
