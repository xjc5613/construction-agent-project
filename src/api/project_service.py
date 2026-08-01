# -*- coding: utf-8 -*-
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config.settings import PROJECTS_DIR
from src.ingestion.models import ParsedDocument
from src.ingestion.parsers import parse_file, validate_upload
from src.library import LibraryRepository

from .topic_service import (
    _clean_text,
    extract_topics_from_document,
    refine_topics_with_llm,
)


def content_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ProjectService:
    def __init__(self, repository: Optional[LibraryRepository] = None):
        self.repository = repository or LibraryRepository()

    def add_text_material(self, project_id: str, title: str, content: str) -> Dict[str, Any]:
        if not self.repository.get_project(project_id):
            raise ValueError("预测项目不存在")
        cleaned = _clean_text(content)
        if not cleaned:
            raise ValueError("材料内容不能为空")
        return self.repository.add_material({
            "project_id": project_id, "title": title.strip(), "source_type": "text",
            "checksum": content_checksum(content.encode("utf-8")),
            "content": content, "cleaned_content": cleaned,
            "parse_metadata": {"source": "pasted_text"},
        })

    def add_file_material(
        self, project_id: str, filename: str, media_type: str, content: bytes
    ) -> Dict[str, Any]:
        if not self.repository.get_project(project_id):
            raise ValueError("预测项目不存在")
        safe_name = validate_upload(filename, media_type, len(content))
        material_id = f"material_{uuid4().hex[:16]}"
        directory = PROJECTS_DIR / project_id / "materials"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{material_id}{Path(safe_name).suffix.lower()}"
        path.write_bytes(content)
        parsed = parse_file(path)
        if not isinstance(parsed, ParsedDocument):
            raise ValueError("项目研究材料必须是文档格式")
        if not parsed.text.strip():
            raise ValueError("文件没有提取到可用文本")
        return self.repository.add_material({
            "material_id": material_id, "project_id": project_id,
            "title": parsed.title or Path(safe_name).stem,
            "source_type": Path(safe_name).suffix.lower().lstrip("."),
            "original_filename": safe_name, "checksum": content_checksum(content),
            "content": parsed.text, "cleaned_content": _clean_text(parsed.text),
            "stored_path": str(path), "parse_status": "needs_review" if parsed.warnings else "ready",
            "parse_metadata": {
                **parsed.metadata, "text_coverage": parsed.text_coverage,
                "warnings": parsed.warnings,
            },
        })

    def extract_topics(
        self, project_id: str, material_ids: List[str],
        refine_with_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        materials = []
        for material_id in material_ids:
            material = self.repository.get_material(material_id)
            if not material or material["project_id"] != project_id:
                raise ValueError(f"项目材料不存在: {material_id}")
            materials.append(material)
        candidates: List[Dict[str, Any]] = []
        for material in materials:
            extracted = extract_topics_from_document(
                material["cleaned_content"], material["material_id"], include_seed_topics=True
            )
            if refine_with_llm:
                extracted = refine_topics_with_llm(
                    extracted, material["cleaned_content"]
                )
            signals = self._material_signals(material["cleaned_content"])
            for candidate in extracted:
                if candidate["topic_name"] == "待校准技术主题":
                    candidate["topic_name"] = self._discover_topic_name(
                        material["title"], material["cleaned_content"]
                    )
                evidence = [
                    {
                        "material_id": material["material_id"],
                        "title": material["title"], "ipc": item.get("ipc", ""),
                        "content": item.get("quote") or item.get("trend", ""),
                        "location": "材料正文", "extraction_method": "rule",
                        **signals,
                    }
                    for item in candidate.get("ipc_evidence", [])
                ]
                if not evidence:
                    evidence = [{
                        "material_id": material["material_id"], "title": material["title"],
                        "content": abstract, "location": "材料正文",
                        "extraction_method": "rule", **signals,
                    } for abstract in candidate.get("sample_abstracts", [])]
                candidates.append(self.repository.save_topic({
                    "project_id": project_id, "topic_name": candidate["topic_name"],
                    "description": candidate.get("example", ""),
                    "keywords": candidate.get("keywords", []), "evidence": evidence,
                    "fusion_pairs": candidate.get("fusion_pairs", []),
                    "evidence_score": candidate.get("evidence_score", 0),
                    "requires_review": candidate.get("requires_review", True),
                    "selected": candidate.get("selected", True), "status": "candidate",
                }))
        self.repository.update_project_status(project_id, "topics_review")
        return candidates

    @staticmethod
    def _material_signals(content: str) -> Dict[str, List[str]]:
        years = list(dict.fromkeys(re.findall(r"\b(?:19|20)\d{2}\b", content)))[:20]
        indicators = [
            term for term in (
                "专利量", "申请量", "增长率", "度中心度", "中介中心度",
                "融合概率", "TRL", "成熟度",
            )
            if term.lower() in content.lower()
        ]
        directions = list(dict.fromkeys(re.findall(
            r"([\u4e00-\u9fffA-Za-z0-9]{3,24}(?:方向|路线|场景|方法|技术))",
            content,
        )))[:12]
        return {
            "years": years,
            "indicators": indicators,
            "research_directions": directions,
        }

    @staticmethod
    def _discover_topic_name(title: str, content: str) -> str:
        title = re.sub(r"(研究|分析|报告|材料|论文)$", "", title.strip())
        if title and title not in {"智能建造技术", "研究文档"}:
            return title[:120]
        matches = re.findall(r"([\u4e00-\u9fffA-Za-z0-9]{4,24}(?:技术|系统|平台|方法))", content)
        return matches[0][:120] if matches else "新兴技术主题"
