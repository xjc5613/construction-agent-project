import json
import zipfile
from pathlib import Path

import pytest

from src.research.publication import ResearchBundleService
from src.research.visualization import ChartSeries, ScientificChartData, ScientificFigureRenderer, visual_accessibility_audit


def _chart(kind="roadmap_swimlane"):
    values = [{"start": 2025, "end": 2030, "label": "验证", "trl": 4},
              {"start": 2030, "end": 2035, "label": "示范", "trl": 6},
              {"start": 2035, "end": 2040, "label": "规模化", "trl": 8}]
    return ScientificChartData(
        figure_number="图4-1", chart_kind=kind, title="技术路线图",
        caption="三种情景表示条件差异，不表示因果关系。", source_note="冻结研究快照",
        sample_size=20, cutoff="2025-10-01",
        series=[ChartSeries(series_id="baseline", label="基准情景", evidence_status="predicted", values=values)],
    )


def _dossier():
    milestones = [
        {"year": 2030, "title": "原型验证", "trl": 4, "evidence_ids": ["p1"]},
        {"year": 2035, "title": "工程示范", "trl": 6, "dependencies": ["原型验证"]},
        {"year": 2040, "title": "规模应用", "trl": 8, "dependencies": ["工程示范"]},
    ]
    return ResearchBundleService().assemble_dossier({
        "theme_id": "theme-1", "theme_name": "具身建造机器人", "definition": "多源感知与施工机器人融合。",
        "ipc_pairs": [{"ipc1": "B25J9/16", "ipc2": "E04G21/00"}], "patent_evidence_ids": ["p1"],
        "paper_evidence_ids": ["a1"], "probability_status": "uncalibrated", "probability": None,
        "interval": None, "limitations": [], "partial_2025": True,
        "scenarios": {"baseline": milestones, "accelerated": milestones, "constrained": milestones},
        "review_refs": ["review-1"],
    })


def test_chart_contract_is_deterministic_and_exports_vector_and_600_dpi_png(tmp_path):
    chart = _chart()
    assert chart.checksum == _chart().checksum
    result = ScientificFigureRenderer().render(chart, tmp_path)
    assert Path(result["png"]).is_file() and Path(result["svg"]).is_file()
    assert Path(result["png"]).stat().st_size > 10_000
    stored = json.loads(Path(result["chart_data"]).read_text(encoding="utf-8"))
    assert stored["series"][0]["evidence_status"] == "predicted"
    assert "不表示因果" in result["accessibility_description"]
    repeated = ScientificFigureRenderer().render(chart, tmp_path / "repeat")
    assert Path(result["png"]).read_bytes() == Path(repeated["png"]).read_bytes()
    audit = visual_accessibility_audit(chart)
    assert audit["passed"] and audit["grayscale_compatible"] and audit["status_not_color_only"]


def test_dossier_rejects_false_probability_and_non_cumulative_roadmap():
    base = _dossier().model_dump()
    base.update(probability_status="uncalibrated", probability=.8, checksum="")
    with pytest.raises(ValueError, match="不得呈现为概率"):
        ResearchBundleService().assemble_dossier(base)
    base = _dossier().model_dump(); base["scenarios"]["baseline"] = base["scenarios"]["baseline"][:2]; base["checksum"] = ""
    with pytest.raises(ValueError, match="缺少"):
        ResearchBundleService().assemble_dossier(base)


def test_research_bundle_is_structured_gated_and_integrity_verifiable(tmp_path):
    service = ResearchBundleService()
    with pytest.raises(ValueError, match="发布门"):
        service.export(tmp_path / "blocked", {"project_id": "p"}, [_dossier()], [], [], [], {"publishable": False})
    result = service.export(tmp_path / "published", {"project_id": "p"}, [_dossier()], [_chart()],
                            [{"id": "a1"}], [{"review_id": "review-1"}], {"publishable": True})
    assert Path(result["bundle"]).is_file()
    with zipfile.ZipFile(result["bundle"]) as bundle:
        assert {"report.md", "dossiers.json", "bibliography.json", "validation-artifacts.json",
                "limitations.json", "review-log.json", "manifest.json"} <= set(bundle.namelist())
    repeated = service.export(tmp_path / "published", {"project_id": "p"}, [_dossier()], [_chart()],
                              [{"id": "a1"}], [{"review_id": "review-1"}], {"publishable": True})
    assert repeated["bundle_checksum"] == result["bundle_checksum"]
    assert service.verify(tmp_path / "published")["valid"] is True
    (tmp_path / "published" / "report.md").write_text("tampered", encoding="utf-8")
    assert service.verify(tmp_path / "published")["valid"] is False


def test_citation_validation_rejects_evidence_outside_frozen_snapshot():
    service = ResearchBundleService()
    service.validate_citations([_dossier()], {"p1", "a1"})
    with pytest.raises(ValueError, match="未知证据"):
        service.validate_citations([_dossier()], {"a1"})
