# -*- coding: utf-8 -*-
"""Immutable forecast dossiers, cumulative roadmaps and reproducible bundles."""

import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field, model_validator

from src.research.repository import canonical_checksum
from src.research.visualization import ScientificChartData, ScientificFigureRenderer


class Milestone(BaseModel):
    year: int
    title: str
    trl: Optional[int] = Field(default=None, ge=1, le=9)
    dependencies: List[str] = Field(default_factory=list)
    indicators: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    uncertainty: str = "not_estimable"


class ThemeDossier(BaseModel):
    schema_version: str = "theme-dossier-v1"
    theme_id: str
    theme_name: str
    definition: str
    ipc_pairs: List[Dict[str, Any]]
    patent_evidence_ids: List[str]
    paper_evidence_ids: List[str]
    probability_status: str
    probability: Optional[float] = Field(default=None, ge=0, le=1)
    interval: Optional[List[float]] = None
    limitations: List[str]
    validation_limits: List[str] = Field(default_factory=list)
    evidence_conflicts: List[str] = Field(default_factory=list)
    expert_overrides: List[str] = Field(default_factory=list)
    stability_status: str = "not_evaluated"
    scenarios: Dict[str, List[Milestone]]
    review_refs: List[str]
    checksum: str = ""

    @model_validator(mode="after")
    def validate_dossier(self):
        if self.probability_status != "calibrated" and self.probability is not None:
            raise ValueError("未校准结果不得呈现为概率")
        required = {2030, 2035, 2040}
        for name, milestones in self.scenarios.items():
            if not required.issubset({item.year for item in milestones}):
                raise ValueError("%s 情景缺少 2030/2035/2040 累积节点" % name)
            ordered = sorted((item for item in milestones if item.trl is not None), key=lambda item: item.year)
            if any(right.trl < left.trl for left, right in zip(ordered, ordered[1:])):
                raise ValueError("TRL 不得随时间倒退")
        if not self.checksum:
            self.checksum = canonical_checksum(self.model_dump(exclude={"checksum"}))
        return self


class ResearchBundleService:
    def assemble_dossier(self, payload: Dict[str, Any]) -> ThemeDossier:
        limitations = list(payload.get("limitations") or [])
        if payload.get("partial_2025"):
            limitations.append("2025 年为截至研究截止日的部分年度，排名与网络强度需结合敏感性分析解释。")
        if payload.get("stability_status") == "unstable":
            limitations.append("该候选在预设敏感性检验中不稳定。")
        clean = {key: value for key, value in payload.items() if key != "partial_2025"}
        return ThemeDossier(**{**clean, "limitations": sorted(set(limitations))})

    def export(self, output_dir: Path, project: Dict[str, Any], dossiers: Iterable[ThemeDossier],
               charts: Iterable[ScientificChartData], bibliography: Iterable[Dict[str, Any]],
               reviews: Iterable[Dict[str, Any]], gates: Dict[str, Any],
               validation_artifacts: Optional[Dict[str, Any]] = None,
               known_evidence_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
        dossier_values = [item.model_dump() for item in dossiers]
        if not gates.get("publishable", False):
            raise ValueError("发布门未全部通过，不能生成最终研究包")
        if known_evidence_ids is not None:
            self.validate_citations(dossiers, known_evidence_ids)
        files: List[Path] = []
        structured = {"schema_version": "research-bundle-v1", "project": project,
                      "dossiers": dossier_values, "bibliography": list(bibliography),
                      "review_log": list(reviews), "publication_gates": gates}
        structured_path = output_dir / "structured-artifacts.json"
        structured_path.write_text(json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8"); files.append(structured_path)
        supplements = {
            "dossiers.json": dossier_values, "bibliography.json": structured["bibliography"],
            "review-log.json": structured["review_log"], "validation-artifacts.json": validation_artifacts or {},
            "limitations.json": [{"theme_id": item["theme_id"], "limitations": item["limitations"],
                                   "validation_limits": item["validation_limits"], "evidence_conflicts": item["evidence_conflicts"],
                                   "expert_overrides": item["expert_overrides"]} for item in dossier_values],
        }
        for filename, value in supplements.items():
            path = output_dir / filename
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"); files.append(path)
        report = output_dir / "report.md"; report.write_text(self._report(structured), encoding="utf-8"); files.append(report)
        chart_dir = output_dir / "figures"
        for chart in charts:
            rendered = ScientificFigureRenderer().render(chart, chart_dir)
            files.extend(Path(rendered[key]) for key in ("png", "svg", "chart_data"))
        manifest = {"schema_version": "export-manifest-v1", "dependencies": {
            str(path.relative_to(output_dir)): canonical_checksum(path.read_bytes().hex()) for path in files}}
        manifest["checksum"] = canonical_checksum(manifest)
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"); files.append(manifest_path)
        archive = output_dir / "research-bundle.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(files, key=lambda item: str(item.relative_to(output_dir))):
                info = zipfile.ZipInfo(str(path.relative_to(output_dir)), date_time=(2025, 10, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                bundle.writestr(info, path.read_bytes())
        return {"bundle": str(archive), "manifest": manifest, "file_count": len(files),
                "bundle_checksum": canonical_checksum(archive.read_bytes().hex())}

    @staticmethod
    def verify(output_dir: Path) -> Dict[str, Any]:
        output_dir = Path(output_dir)
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        differences = []
        for relative, expected in manifest["dependencies"].items():
            path = output_dir / relative
            actual = canonical_checksum(path.read_bytes().hex()) if path.exists() else None
            if actual != expected: differences.append({"path": relative, "expected": expected, "actual": actual})
        return {"valid": not differences, "differences": differences, "manifest_checksum": manifest["checksum"]}

    @staticmethod
    def regenerate_chart(chart_data_path: Path, output_dir: Path) -> Dict[str, Any]:
        chart = ScientificChartData.model_validate_json(Path(chart_data_path).read_text(encoding="utf-8"))
        return ScientificFigureRenderer().render(chart, Path(output_dir))

    @staticmethod
    def validate_citations(dossiers: Iterable[ThemeDossier], known_evidence_ids: Iterable[str]) -> None:
        known = set(known_evidence_ids)
        cited = {identifier for dossier in dossiers for identifier in
                 [*dossier.patent_evidence_ids, *dossier.paper_evidence_ids]}
        unknown = cited - known
        if unknown: raise ValueError("研究包包含未知证据引用: " + ", ".join(sorted(unknown)))

    @staticmethod
    def _report(value: Dict[str, Any]) -> str:
        lines = ["# 面向 2040 的智能建造关键技术预测", "",
                 "> 本报告仅由冻结的结构化产物生成；预测不等同于确定事实。", ""]
        for item in value["dossiers"]:
            lines.extend(["## " + item["theme_name"], "", item["definition"], "",
                          "- 概率状态：" + item["probability_status"],
                          "- IPC 融合对：" + "、".join("%s × %s" % (p.get("ipc1"), p.get("ipc2")) for p in item["ipc_pairs"]),
                          "- 局限：" + ("；".join(item["limitations"]) or "无额外局限记录"),
                          "- 验证限制：" + ("；".join(item["validation_limits"]) or "无"),
                          "- 证据冲突：" + ("；".join(item["evidence_conflicts"]) or "无"),
                          "- 专家覆盖：" + ("；".join(item["expert_overrides"]) or "无"),
                          "- 稳定性：" + item["stability_status"], ""])
        return "\n".join(lines)
