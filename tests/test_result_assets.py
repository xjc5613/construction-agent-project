# -*- coding:utf-8 -*-
import importlib
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.storage import WorkbenchStorage

api_module = importlib.import_module("src.api.app")


class ResultAssetsApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = WorkbenchStorage(Path(self.temp_dir.name))
        self.original_storage = api_module.storage
        api_module.storage = self.storage
        self.client = TestClient(api_module.app)
        self.job_id = "forecast_assets"
        self.topic_id = "topic_assembly"
        self.storage.save_job(self.job_id, {"job_id": self.job_id})
        self.storage.save_job_artifact(self.job_id, "result.json", {
            "topics": [{
                "topic_id": self.topic_id, "topic_name": "装配式建筑技术",
                "keywords": ["预制构件"], "ipc_evidence": [],
            }],
            "per_topic_roadmaps": [{
                "topic_name": "装配式建筑技术",
                "roadmap": {
                    "2030": {"stage_description": "验证", "milestones": [{"name": "节点库", "trl_level": 5, "uncertainty_level": "medium"}]},
                    "2035": {"stage_description": "应用", "milestones": [{"name": "规模化", "trl_level": 7, "uncertainty_level": "medium"}]},
                    "2040": {"stage_description": "成熟", "milestones": [{"name": "闭环", "trl_level": 9, "uncertainty_level": "low"}]},
                },
            }],
        })
        asset_dir = self.storage.job_dir(self.job_id) / "assets" / self.topic_id
        asset_dir.mkdir(parents=True)
        image_path = asset_dir / "combined.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nmock")
        self.asset_id = "asset_combined"
        self.storage.save_job_artifact(self.job_id, "assets.json", {
            "assets": [{
                "asset_id": self.asset_id, "topic_id": self.topic_id,
                "topic_name": "装配式建筑技术", "kind": "combined",
                "title": "综合分析图", "media_type": "image/png",
                "filename": "combined.png", "relative_path": f"{self.topic_id}/combined.png",
                "url": f"/api/forecast/jobs/{self.job_id}/assets/{self.asset_id}",
                "download_url": f"/api/forecast/jobs/{self.job_id}/assets/{self.asset_id}?download=true",
            }],
            "failed_assets": [],
        })

    def tearDown(self):
        api_module.storage = self.original_storage
        self.temp_dir.cleanup()

    def test_topics_and_topic_detail(self):
        response = self.client.get(f"/api/forecast/jobs/{self.job_id}/topics?q=装配")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["asset_count"], 1)
        detail = self.client.get(f"/api/forecast/jobs/{self.job_id}/topics/{self.topic_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("2040", detail.json()["stages"])

    def test_asset_is_served_only_by_registered_id(self):
        response = self.client.get(f"/api/forecast/jobs/{self.job_id}/assets/{self.asset_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(self.client.get(f"/api/forecast/jobs/{self.job_id}/assets/../../job.json").status_code, 404)
