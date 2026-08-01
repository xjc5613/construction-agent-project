# -*- coding:utf-8 -*-
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import JOBS_DIR, PROJECTS_DIR


class WorkbenchStorage:
    """File-backed storage kept separate from the existing forecast cache."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            self.base_dir = JOBS_DIR.parent
            legacy_project_dir = PROJECTS_DIR / "legacy-default"
            self.documents_dir = legacy_project_dir / "documents"
            self.topics_path = legacy_project_dir / "topics" / "topics.json"
            self.jobs_dir = JOBS_DIR
        else:
            self.base_dir = Path(base_dir)
            self.documents_dir = self.base_dir / "documents"
            self.topics_path = self.base_dir / "topics" / "topics.json"
            self.jobs_dir = self.base_dir / "jobs"
        for path in (self.documents_dir, self.topics_path.parent, self.jobs_dir):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    def save_document(self, document: Dict[str, Any]) -> None:
        self._write_json(self.documents_dir / f"{document['document_id']}.json", document)

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        path = self.documents_dir / f"{document_id}.json"
        return self._read_json(path, None)

    def list_topics(self) -> List[Dict[str, Any]]:
        return self._read_json(self.topics_path, [])

    def save_topics(self, topics: List[Dict[str, Any]]) -> None:
        self._write_json(self.topics_path, topics)

    def job_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_job(self, job_id: str, job: Dict[str, Any]) -> None:
        self._write_json(self.job_dir(job_id) / "job.json", job)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._read_json(self.jobs_dir / job_id / "job.json", None)

    def save_job_artifact(self, job_id: str, name: str, payload: Any) -> Path:
        path = self.job_dir(job_id) / name
        self._write_json(path, payload)
        return path

    def get_job_artifact(self, job_id: str, name: str, default: Any = None) -> Any:
        return self._read_json(self.jobs_dir / job_id / name, default)
