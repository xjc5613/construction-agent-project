# -*- coding: utf-8 -*-
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config.settings import PROJECTS_DIR
from src.ingestion.models import ParsedDocument
from src.ingestion.parsers import parse_file, validate_upload
from src.library import (
    DatasetEligibilityResolver,
    LibraryRepository,
    TechnologyRepository,
)
from src.library.constants import ANALYSIS_KINDS, LEGACY_TOPIC_MAPPINGS

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

    def add_text_material(
        self, project_id: str, title: str, content: str,
        analysis_kind: str = "integrated_analysis",
    ) -> Dict[str, Any]:
        if not self.repository.get_project(project_id):
            raise ValueError("预测项目不存在")
        if analysis_kind not in ANALYSIS_KINDS:
            raise ValueError("分析材料类型无效")
        cleaned = _clean_text(content)
        if not cleaned:
            raise ValueError("材料内容不能为空")
        review_status = self._review_status(analysis_kind, cleaned)
        return self.repository.add_material({
            "project_id": project_id, "title": title.strip(), "source_type": "text",
            "checksum": content_checksum(content.encode("utf-8")),
            "content": content, "cleaned_content": cleaned,
            "analysis_kind": analysis_kind, "review_status": review_status,
            "parse_metadata": {"source": "pasted_text"},
        })

    def add_file_material(
        self, project_id: str, filename: str, media_type: str, content: bytes,
        analysis_kind: str = "integrated_analysis",
    ) -> Dict[str, Any]:
        if not self.repository.get_project(project_id):
            raise ValueError("预测项目不存在")
        if analysis_kind not in ANALYSIS_KINDS:
            raise ValueError("分析材料类型无效")
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
        review_status = self._review_status(analysis_kind, parsed.text)
        return self.repository.add_material({
            "material_id": material_id, "project_id": project_id,
            "title": parsed.title or Path(safe_name).stem,
            "source_type": Path(safe_name).suffix.lower().lstrip("."),
            "original_filename": safe_name, "checksum": content_checksum(content),
            "content": parsed.text, "cleaned_content": _clean_text(parsed.text),
            "stored_path": str(path), "parse_status": "needs_review" if parsed.warnings else "ready",
            "analysis_kind": analysis_kind, "review_status": review_status,
            "parse_metadata": {
                **parsed.metadata, "text_coverage": parsed.text_coverage,
                "warnings": parsed.warnings,
            },
        })

    def extract_topics(
        self, project_id: str, material_ids: List[str],
        refine_with_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        project = self.repository.get_project(project_id)
        if not project:
            raise ValueError("预测项目不存在")
        technology_repository = TechnologyRepository(self.repository.db)
        leaves = (
            technology_repository.descendants(
                project["technology_node_id"], level=3, active_only=True
            )
            if project.get("technology_node_id") else []
        )
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
                technologies = self._match_technologies(
                    candidate, material["cleaned_content"], leaves
                )
                scope = DatasetEligibilityResolver(self.repository).resolve(
                    project,
                    [
                        item["technology_node_id"]
                        for item in technologies
                    ],
                )
                stage_datasets = scope["eligible_datasets"]
                if stage_datasets:
                    evidence.append({
                        "title": "阶段化基础证据",
                        "content": "；".join(
                            f"{item.get('technology_name')} {item.get('period_code')} "
                            f"v{item.get('version')}"
                            for item in stage_datasets[:20]
                        ),
                        "location": "基础数据中心",
                        "extraction_method": "stage_evidence",
                        "dataset_ids": [
                            item["dataset_id"] for item in stage_datasets
                        ],
                    })
                candidates.append(self.repository.save_topic({
                    "project_id": project_id, "topic_name": candidate["topic_name"],
                    "description": candidate.get("example", ""),
                    "keywords": candidate.get("keywords", []), "evidence": evidence,
                    "fusion_pairs": candidate.get("fusion_pairs", []),
                    "evidence_score": candidate.get("evidence_score", 0),
                    "requires_review": (
                        candidate.get("requires_review", True) or not technologies
                    ),
                    "selected": candidate.get("selected", True), "status": "candidate",
                    "technologies": technologies,
                }))
        self.repository.update_project_status(project_id, "topics_review")
        return candidates

    @staticmethod
    def _review_status(analysis_kind: str, content: str) -> str:
        has_ipc = bool(re.search(r"\b[A-H]\d{2}[A-Z]", content, re.IGNORECASE))
        has_year = bool(re.search(r"\b(?:19|20)\d{2}\b", content))
        has_paper = any(term in content for term in ("论文", "文献", "摘要", "关键词"))
        if analysis_kind == "ipc_analysis" and not (has_ipc and has_year):
            return "needs_review"
        if analysis_kind == "paper_analysis" and not (has_paper and has_year):
            return "needs_review"
        if analysis_kind == "integrated_analysis" and not (has_ipc and has_paper):
            return "needs_review"
        return "ready"

    @staticmethod
    def _match_technologies(
        candidate: Dict[str, Any], content: str,
        leaves: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        mapped_ids = LEGACY_TOPIC_MAPPINGS.get(candidate.get("topic_name", ""), [])
        haystack = " ".join([
            candidate.get("topic_name", ""), content,
            *candidate.get("keywords", []),
        ]).lower()
        scored = []
        for leaf in leaves:
            terms = [leaf["name"], *leaf.get("keywords", []), *leaf.get("aliases", [])]
            score = sum(1 for term in terms if term and term.lower() in haystack)
            if leaf["node_id"] in mapped_ids:
                score += 5
            if score:
                scored.append((score, leaf))
        scored.sort(key=lambda item: (-item[0], item[1]["sort_order"]))
        selected = [item[1] for item in scored[:5]]
        return [
            {
                "technology_node_id": leaf["node_id"],
                "is_primary": index == 0,
                "relevance": min(1.0, scored[index][0] / 5) if index < len(scored) else 0.2,
                "source": "rule",
            }
            for index, leaf in enumerate(selected)
        ]

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
