# -*- coding:utf-8 -*-
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.forecast_service import create_job, run_forecast_job
from src.api.storage import WorkbenchStorage

api_module = importlib.import_module("src.api.app")


class WorkbenchApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = WorkbenchStorage(Path(self.temp_dir.name))
        self.original_storage = api_module.storage
        api_module.storage = self.storage
        self.client = TestClient(api_module.app)

    def tearDown(self):
        api_module.storage = self.original_storage
        self.temp_dir.cleanup()

    def test_document_to_topic_normalization(self):
        response = self.client.post("/api/documents", json={
            "title": "装配式建筑研究",
            "content": "涉及预制构件、工厂制造及现场安装。E04B-001度中心度0.1779。E04B与B28B融合概率为0.76。",
            "source_type": "text",
        })
        self.assertEqual(response.status_code, 201)
        document_id = response.json()["document_id"]

        response = self.client.post("/api/topics/extract", json={
            "document_ids": [document_id],
            "seed_topics": "use_existing",
            "extraction_mode": "rules_only",
        })
        self.assertEqual(response.status_code, 200)
        topics = response.json()
        self.assertTrue(topics)
        topic = next(item for item in topics if item["topic_name"] == "装配式建筑技术")
        self.assertEqual(topic["ipc_evidence"][0]["ipc"], "E04B-001")

        response = self.client.patch(f"/api/topics/{topic['topic_id']}", json={"selected": False})
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/api/topics/normalize", json={"topic_ids": [topic["topic_id"]]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["round1_inputs"], [])

    def test_invalid_document_is_rejected(self):
        response = self.client.post("/api/documents", json={
            "title": "空文档",
            "content": "   ",
            "source_type": "text",
        })
        self.assertEqual(response.status_code, 422)


class ForecastServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = WorkbenchStorage(Path(self.temp_dir.name))
        self.topic = {
            "topic_id": "topic_assembly",
            "topic_name": "装配式建筑技术",
            "keywords": ["预制", "构件"],
            "example": "钢结构装配式建筑",
            "ipc_evidence": [{
                "ipc": "E04B-001",
                "trend": "度中心度0.1779",
                "quote": "预制构件",
                "document_id": "doc_001",
            }],
            "ipc_trend": "E04B-001度中心度0.1779",
            "fusion_pairs": [{"ipc1": "E04B", "ipc2": "B28B", "prob": 0.76}],
            "sample_abstracts": ["涉及预制构件、工厂制造及现场安装。"],
            "operator_notes": "",
            "evidence_score": 80,
            "requires_review": False,
            "selected": True,
        }
        self.storage.save_topics([self.topic])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mocked_job_generates_results_and_charts(self):
        job = create_job(self.storage, [self.topic["topic_id"]], {
            "enable_per_topic_roadmap": True,
            "enable_self_consistency": False,
            "enable_multi_agent_debate": False,
            "enable_multi_model": False,
            "force_rerun": False,
        })
        round1 = [{
            "topic_name": self.topic["topic_name"],
            "bottlenecks_2030_2035": ["节点标准化不足（依据：E04B-001）"],
            "breakthroughs_by_2040": ["智能生产线（依据：E04B与B28B）"],
            "reasoning_chain": [{"evidence": "E04B-001"}],
            "confidence": 72,
        }]
        roadmaps = [{
            "topic_name": self.topic["topic_name"],
            "roadmap": {
                "2025": {"milestones": [{"trl_level": 3, "uncertainty_level": "low"}]},
                "2030": {"milestones": [{"name": "节点库", "trl_level": 5, "uncertainty_level": "medium"}]},
                "2035": {"milestones": [{"name": "规模应用", "trl_level": 7, "uncertainty_level": "medium"}]},
                "2040": {"milestones": [{"name": "全生命周期", "trl_level": 9, "uncertainty_level": "high"}]},
            },
        }]
        asset_index = {
            "job_id": job["job_id"],
            "assets": [],
            "failed_assets": [],
        }
        with patch("src.api.forecast_service.run_round1", return_value=round1), \
             patch("src.api.forecast_service.run_round2", return_value={"new_paradigm_name": "协同建造"}), \
             patch("src.api.forecast_service.run_round3", return_value=[]), \
             patch("src.api.forecast_service.run_all_topics_roadmap", return_value=roadmaps), \
             patch("src.api.forecast_service.generate_job_assets", return_value=asset_index):
            run_forecast_job(self.storage, job["job_id"])
        saved_job = self.storage.get_job(job["job_id"])
        self.assertEqual(saved_job["status"], "partial_failed")
        self.assertEqual(
            self.storage.get_job_artifact(job["job_id"], "result.json")["stage_quality"]["round3"],
            "missing",
        )
        charts = self.storage.get_job_artifact(job["job_id"], "charts.json")
        self.assertIn("trl_series", charts)
        self.assertEqual(charts["fusion_network"][0]["source"], "E04B")


if __name__ == "__main__":
    unittest.main()
