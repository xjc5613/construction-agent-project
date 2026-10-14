# -*- coding: utf-8 -*-
import json
import importlib
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.library import LibraryDatabase, LibraryRepository
from src.research.claim_validation import ClaimValidationSuite
from src.research.evidence_packets import EvidencePacketService
from src.research.evolution_schemas import DevelopmentClaim, EvaluationManifest, RoadmapMilestone
from src.research.method_evaluation import ForecastMethodEvaluator
from src.research.graph import LocalGraphCheckpointer
from src.research.thesis_graph import (
    ThesisAgentRoles, ThesisDeliberationGraph, ThesisGraphContext,
)
from src.research.thesis_repository import ThesisRepository


FIXTURE = Path(__file__).parent / "fixtures" / "evolution_packet.json"


class ThesisEvolutionAgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = LibraryDatabase(Path(self.tmp.name) / "library.sqlite3")
        self.library = LibraryRepository(self.db)
        self.project = self.library.create_project("thesis agent")
        self.repository = ThesisRepository(self.db)
        self.service = EvidencePacketService(self.repository)
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def frozen_packet(self, packet_id="chapter4"):
        row = self.service.create_from_draft(
            self.payload, self.project["project_id"], packet_id)
        self.service.review(row["packet_version_id"])
        return self.service.freeze(row["packet_version_id"])

    def reserve_job(self, job_id):
        self.library.reserve_forecast_job(
            job_id, self.project["project_id"], request_checksum=job_id,
            idempotency_key=job_id, options={"revision_limit": 1},
        )
        self.library.update_forecast_job_status(job_id, "running")

    def test_packet_unknown_mapping_version_and_immutability(self):
        self.payload["records"][1]["values"]["unknown_metric"] = None
        first = self.service.create_from_draft(
            self.payload, self.project["project_id"], "chapter4")
        self.assertIsNone(first["payload"]["records"][1]["values"]["unknown_metric"])
        self.assertEqual(first["attachments"][0]["mapping_state"],
                         "reported_but_not_supplied")
        self.assertEqual(first["attachments"][0]["row_count"], 926)
        same = self.repository.create_packet(
            self.service.import_draft(
                self.payload, self.project["project_id"], "chapter4", version=1))
        self.assertEqual(first["checksum"], same["checksum"])
        self.service.review(first["packet_version_id"])
        self.service.freeze(first["packet_version_id"])

        changed = json.loads(json.dumps(self.payload))
        changed["records"][1]["statement"] = "new content"
        second = self.service.create_from_draft(
            changed, self.project["project_id"], "chapter4")
        self.assertEqual(second["version"], 2)
        diff = self.service.diff(first["packet_version_id"], second["packet_version_id"])
        self.assertEqual(diff["changed"], ["N1-B25J011"])
        with self.assertRaises(ValueError):
            self.repository.create_packet(
                self.service.import_draft(changed, self.project["project_id"], "chapter4", 1))

    def test_v9_migration_preserves_completed_legacy_job_and_v3_checkpoint(self):
        self.reserve_job("legacy-job")
        self.library.update_forecast_job_status("legacy-job", "completed", progress=1)
        checkpointer = LocalGraphCheckpointer(self.library)
        thread_id = checkpointer.create_thread("legacy-job")
        checkpointer.save(thread_id, "fusion_review", {"schema_version": "v3", "value": 7})
        with self.db.transaction() as connection:
            for table in (
                "forecast_method_evaluations", "thesis_agent_call_traces",
                "claim_terminal_states", "claim_adjudications", "claim_review_findings",
                "development_claim_versions", "evolution_evidence_attachments",
                "evolution_evidence_records", "evolution_evidence_sources",
                "evolution_evidence_packets",
            ):
                connection.execute(f"DROP TABLE {table}")
            connection.execute("ALTER TABLE forecast_jobs DROP COLUMN run_manifest_json")
            connection.execute("ALTER TABLE forecast_jobs DROP COLUMN evolution_packet_version_id")
            connection.execute("ALTER TABLE forecast_jobs DROP COLUMN job_mode")
            connection.execute("DELETE FROM schema_migrations WHERE version=9")
        migrated = LibraryRepository(LibraryDatabase(self.db.path))
        job = migrated.get_forecast_job("legacy-job")
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["job_mode"], "legacy_read_only")
        restored = LocalGraphCheckpointer(migrated).load(thread_id)
        self.assertEqual(restored["value"], 7)

    def test_unreviewed_discovery_cannot_enter_packet(self):
        self.frozen_packet()
        with self.assertRaises(ValueError):
            self.service.import_reviewed_discovery(
                "chapter4", {"candidate_id": "C01", "reviewed": False}, ["T03"],
                "reviewer", {"source_kind": "artifact", "locator": "fusion/run-1"})
        imported = self.service.import_reviewed_discovery(
            "chapter4", {
                "candidate_id": "C01", "reviewed": True,
                "statement": "经审核的功能联系候选",
                "model_provenance": {"model": "deterministic-fusion-v1"},
            }, ["T03"], "researcher-a",
            {"source_kind": "artifact", "locator": "fusion/run-1"},
        )
        derived = next(item for item in imported["records"]
                       if item["evidence_kind"] == "derived_model_evidence")
        self.assertEqual(derived["evidence_kind"], "derived_model_evidence")
        self.assertEqual(derived["object_ids"], ["T03"])
        self.assertIn("不能自动改写论文主题", derived["does_not_support"])

    def test_deterministic_boundaries_and_trl_contract(self):
        packet = self.service.import_draft(
            self.payload, self.project["project_id"], "chapter4")
        claim = DevelopmentClaim(
            claim_id="robot-growth", version=1, object_ids=["T03"],
            claim_type="conditional_extrapolation", target_period="2026_2030",
            statement="机器人集群协同主题中心度达到0.1462并已实现效率提高",
            evidence_ids=["N3-B25J011"], enabling_conditions=["工程验证"],
            support_level="conditional_support", support_reason="IPC网络观察",
        )
        categories = {item.category for item in ClaimValidationSuite().validate(claim, packet)}
        self.assertIn("ipc_to_theme", categories)
        self.assertIn("network_to_performance", categories)

        additive = claim.model_copy(update={
            "claim_id": "additive-direction", "object_ids": ["T08"],
            "statement": "B33Y-070度中心度由0.1257升至0.0951",
            "evidence_ids": ["N2-B33Y070", "N3-B33Y070"],
        })
        numeric = ClaimValidationSuite().numeric.validate(
            additive, packet, [{"evidence_id": "N3-B33Y070",
                                "metric": "degree_centrality", "value": 0.1257}])
        self.assertIn("numeric_mismatch", {item.category for item in numeric})

        static = claim.model_copy(update={
            "claim_id": "static-dynamic", "object_ids": ["T02"],
            "statement": "主题关系持续增长并加速融合", "evidence_ids": ["H01"],
        })
        self.assertIn("static_to_dynamic", {
            item.category for item in ClaimValidationSuite().validate(static, packet)})
        irrelevant = claim.model_copy(update={
            "claim_id": "irrelevant-source", "statement": "机器人协同需要验证",
            "evidence_ids": ["Q08"],
        })
        self.assertIn("object_evidence_scope", {
            item.category for item in ClaimValidationSuite().validate(irrelevant, packet)})
        paraphrase = claim.model_copy(update={
            "claim_id": "paraphrase-only", "statement": "相关系统生产率得到改善",
            "evidence_ids": ["N3-B25J011"],
        })
        self.assertIn("network_to_performance", {
            item.category for item in ClaimValidationSuite().validate(paraphrase, packet)})
        with self.assertRaises(ValidationError):
            RoadmapMilestone(
                milestone_id="m1", object_id="T03", period="2026_2030",
                capability="机器人协同", claim_version_ids=["c:v1"], evidence_ids=["Q03"],
                trl=5,
            )

    def test_conditional_graph_revision_gates_and_cross_job_isolation(self):
        packet = self.frozen_packet()
        self.reserve_job("job-a")

        def role(role_name, payload, schema):
            if role_name == "evolution_analyst":
                return {"summaries": [{
                    "object_id": payload["object"]["object_id"], "observations": [],
                    "missingness": [], "conflicts": [],
                }]}
            if role_name == "proposition_generator":
                if payload["summary"]["object_id"] != "T03":
                    return {"claims": []}
                return {"claims": [{
                    "claim_id": "robot-claim", "version": 1, "object_ids": ["T03"],
                    "claim_type": "conditional_extrapolation", "target_period": "2026_2030",
                    "statement": "在完成现场验证后扩展机器人协同能力",
                    "evidence_ids": ["Q03"], "enabling_conditions": ["现场验证"],
                    "validation_requirements": ["安全和可靠性测试"],
                    "support_level": "conditional_support", "support_reason": "主题事实和条件约束",
                }]}
            if role_name == "reverse_reviewer":
                claim = payload["claim"]
                if claim["version"] == 1:
                    return {"findings": [{
                        "finding_id": "reverse-scope", "claim_id": claim["claim_id"],
                        "claim_version": 1, "reviewer_role": role_name,
                        "check_kind": "scope", "category": "scope_shift", "severity": "warning",
                        "message": "需要收紧适用范围", "remediation": "增加工况边界",
                    }]}
                return {"findings": []}
            if role_name == "engineering_reviewer":
                return {"findings": []}
            if role_name == "adjudicator":
                claim = payload["claim"]
                decision = "revise" if claim["version"] == 1 else "accept"
                return {"adjudications": [{
                    "adjudication_id": f"adj-{claim['version']}", "claim_id": claim["claim_id"],
                    "claim_version": claim["version"], "decision": decision,
                    "finding_ids": ["reverse-scope"] if claim["version"] == 1 else [],
                    "resulting_support_level": "conditional_support", "reason": "独立裁决",
                    "required_changes": ["增加工况边界"] if claim["version"] == 1 else [],
                }]}
            if role_name == "claim_reviser":
                claim = dict(payload["claim"])
                claim.update({
                    "version": 2, "parent_version_id": "robot-claim:v1",
                    "statement": "在受控工况完成现场验证后扩展机器人协同能力",
                    "change_reason": "回应范围审查",
                })
                return claim
            raise AssertionError(role_name)

        graph = ThesisDeliberationGraph(
            ThesisGraphContext(self.library, self.repository, "job-a",
                               self.project["project_id"], revision_limit=1,
                               compute_concurrency=3),
            ThesisAgentRoles(role),
        )
        state = graph.start(packet["packet_version_id"])
        self.assertEqual(state["waiting_for"], "evidence_review")
        # Recreate the graph object to prove recovery uses the durable job checkpoint.
        graph = ThesisDeliberationGraph(
            ThesisGraphContext(self.library, self.repository, "job-a",
                               self.project["project_id"], revision_limit=1,
                               compute_concurrency=3),
            ThesisAgentRoles(role),
        )
        state = graph.decide("evidence_review", "approve", "证据包已核对")
        self.assertEqual(state["waiting_for"], "claim_review")
        self.assertEqual(state["claim_states"]["robot-claim"], "accepted")
        self.assertEqual(len(state["claims"]), 2)
        state = graph.decide(
            "claim_review", "edit", "人工补充更严格的作业边界",
            after={"claim_id": "robot-claim", "changes": {
                "statement": "仅在受控室内工况完成验证后扩展机器人协同能力"}},
        )
        self.assertEqual(state["waiting_for"], "publication_review")
        self.assertEqual(len(state["claims"]), 3)
        self.assertEqual(state["claims"][-1]["parent_version_id"], "robot-claim:v2")
        state = graph.decide("publication_review", "approve", "允许发布")
        self.assertEqual(state["status"], "completed")
        trace = self.repository.job_claim_trace("job-a")
        self.assertEqual(trace["findings"][0]["status"], "closed")
        self.assertEqual(trace["states"][0]["status"], "accepted")
        self.assertEqual([item["claim"]["version"] for item in trace["claims"]], [1, 2, 3])

        self.library.update_forecast_job_status("job-a", "completed")
        self.reserve_job("job-b")
        claim = DevelopmentClaim.model_validate(state["claims"][0])
        stored = self.repository.create_claim_version(
            "job-b", packet["packet_version_id"], claim)
        self.assertTrue(stored["claim_version_id"].startswith("job-b:"))
        self.assertNotEqual(stored["claim_version_id"], trace["claims"][0]["claim_version_id"])

    def test_cancellation_persists_without_model_execution(self):
        packet = self.frozen_packet("cancel-packet")
        self.reserve_job("job-cancel")
        roles = ThesisAgentRoles(lambda role, payload, schema: (_ for _ in ()).throw(
            AssertionError("human evidence gate must precede model execution")))
        graph = ThesisDeliberationGraph(
            ThesisGraphContext(self.library, self.repository, "job-cancel",
                               self.project["project_id"]), roles)
        state = graph.start(packet["packet_version_id"])
        self.assertEqual(state["waiting_for"], "evidence_review")
        recovered = ThesisDeliberationGraph(
            ThesisGraphContext(self.library, self.repository, "job-cancel",
                               self.project["project_id"]), roles).cancel()
        self.assertEqual(recovered["status"], "cancelled")
        self.assertEqual(self.library.get_forecast_job("job-cancel")["status"], "cancelled")

    def test_mixed_outcomes_do_not_block_unrelated_roadmap(self):
        packet = self.frozen_packet("mixed-packet")
        self.reserve_job("job-mixed")

        def role(role_name, payload, schema):
            if role_name == "evolution_analyst":
                return {"summaries": [{"object_id": payload["object"]["object_id"],
                                        "observations": [], "missingness": [], "conflicts": []}]}
            if role_name == "proposition_generator":
                object_id = payload["summary"]["object_id"]
                evidence = {"T03": "Q03", "T08": "Q08"}.get(object_id)
                if not evidence:
                    return {"claims": []}
                return {"claims": [{
                    "claim_id": "mixed-" + object_id, "version": 1,
                    "object_ids": [object_id], "claim_type": "conditional_extrapolation",
                    "target_period": "2026_2030", "statement": object_id + "条件能力",
                    "evidence_ids": [evidence], "enabling_conditions": ["前置验证"],
                    "validation_requirements": ["现场指标"],
                    "support_level": "conditional_support", "support_reason": "主题证据",
                }]}
            if role_name in {"reverse_reviewer", "engineering_reviewer"}:
                return {"findings": []}
            if role_name == "adjudicator":
                claim = payload["claim"]
                decision = "accept" if claim["object_ids"] == ["T03"] else "revise"
                return {"adjudications": [{
                    "adjudication_id": "mixed-adj-" + claim["claim_id"],
                    "claim_id": claim["claim_id"], "claim_version": claim["version"],
                    "decision": decision, "resulting_support_level": "conditional_support",
                    "reason": "分别裁决", "required_changes": ["补充证据"] if decision == "revise" else [],
                }]}
            raise AssertionError(role_name)

        graph = ThesisDeliberationGraph(
            ThesisGraphContext(self.library, self.repository, "job-mixed",
                               self.project["project_id"], revision_limit=0,
                               compute_concurrency=2), ThesisAgentRoles(role))
        state = graph.start(packet["packet_version_id"])
        state = graph.decide("evidence_review", "approve", "ok")
        self.assertEqual(state["waiting_for"], "claim_review")
        self.assertEqual(state["claim_states"]["mixed-T03"], "accepted")
        self.assertEqual(state["claim_states"]["mixed-T08"], "revision_exhausted")
        self.assertEqual([item["object_id"] for item in state["roadmaps"]], ["T03"])
        self.assertEqual(state["coverage"]["accepted"], 1)
        self.assertEqual(state["coverage"]["revision_exhausted"], 1)
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE forecast_jobs SET job_mode='thesis_evolution_forecast',"
                "evolution_packet_version_id=? WHERE job_id='job-mixed'",
                (packet["packet_version_id"],),
            )
        routes = importlib.import_module("src.api.thesis_routes")
        original = routes.repository; routes.repository = self.library
        try:
            exported = TestClient(importlib.import_module("src.api.app").app).get(
                "/api/thesis/jobs/job-mixed/export")
            self.assertEqual(exported.status_code, 200)
            body = exported.json()
            self.assertEqual(body["packet"]["checksum"], packet["checksum"])
            self.assertEqual(body["state"]["coverage"]["revision_exhausted"], 1)
            self.assertEqual(body["packet"]["mapping_attachments"][0]["mapping_state"],
                             "reported_but_not_supplied")
        finally:
            routes.repository = original

    def test_evaluation_uses_null_for_not_estimable(self):
        metrics = ForecastMethodEvaluator.metrics({"arm": {"claims": [], "findings": []}})
        self.assertIsNone(metrics["arm"]["valid_reference_rate"])
        self.assertEqual(
            ForecastMethodEvaluator.substantive_repeatability([])["status"], "not_estimable")
        packet = self.service.import_draft(
            self.payload, self.project["project_id"], "evaluation-packet")
        original = [item.evidence_id for item in packet.records]
        perturbed = ForecastMethodEvaluator.perturb(packet, "reverse_order")
        self.assertEqual([item.evidence_id for item in packet.records], original)
        self.assertEqual([item.evidence_id for item in perturbed.records], list(reversed(original)))
        blind = ForecastMethodEvaluator.blind_review_export({
            "five_role": {"claims": []}, "single_agent": {"claims": []}})
        self.assertTrue(blind["workflow_identity_hidden"])
        self.assertTrue(all(item["annotation"] is None for item in blind["items"]))
        self.assertEqual(ForecastMethodEvaluator.annotation_status(blind)["status"],
                         "insufficient_annotation")

    def test_preregistered_paired_evaluation_keeps_arm_failures_visible(self):
        packet_row = self.frozen_packet("evaluation-frozen")
        packet = self.service.import_draft(
            self.payload, self.project["project_id"], "evaluation-copy")
        packet = packet.model_copy(update={"status": "frozen", "checksum": packet_row["checksum"]})
        manifest = EvaluationManifest(
            evaluation_id="evaluation-1", packet_checksum=packet_row["checksum"],
            object_ids=["T03", "T08"], base_model={"name": "same-model"},
            prompt_versions={"all": "v1"}, budgets={"max_model_calls": 20},
            revision_limit=1, repeats=2, annotation_rules={"blind": True},
            metrics=["reference_validity", "numeric_fidelity"],
        )
        evaluator = ForecastMethodEvaluator(self.repository)
        registered = evaluator.register(packet_row["packet_version_id"], manifest)
        self.assertEqual(registered["status"], "not_run")
        runners = {
            "single_agent": lambda p, c: {"claims": [], "findings": [], "claim_states": {}},
            "five_role": lambda p, c: {"claims": [], "findings": [], "claim_states": {}},
            "staged_reflection": lambda p, c: (_ for _ in ()).throw(RuntimeError("failed arm")),
        }
        result = evaluator.run_paired(packet, manifest, runners, ablation="reverse_review")
        self.assertIn("staged_reflection", result["failures"])
        self.assertIsNone(result["metrics"]["five_role"]["numeric_fidelity_rate"])

    def test_api_requires_frozen_packet_and_starts_at_evidence_gate(self):
        routes = importlib.import_module("src.api.thesis_routes")
        original = routes.repository
        routes.repository = self.library
        try:
            client = TestClient(importlib.import_module("src.api.app").app)
            response = client.post(
                f"/api/thesis/projects/{self.project['project_id']}/evolution-packets",
                json={"packet_id": "api-packet", "payload": self.payload},
            )
            self.assertEqual(response.status_code, 201)
            blocked = client.post(
                f"/api/thesis/projects/{self.project['project_id']}/jobs",
                json={"mode": "thesis_evolution_forecast", "packet_id": "api-packet"},
            )
            self.assertEqual(blocked.status_code, 409)
            packet_version_id = response.json()["packet_version_id"]
            client.post(f"/api/thesis/evolution-packet-versions/{packet_version_id}/review")
            client.post(f"/api/thesis/evolution-packet-versions/{packet_version_id}/freeze")
            started = client.post(
                f"/api/thesis/projects/{self.project['project_id']}/jobs",
                json={"mode": "thesis_evolution_forecast", "packet_id": "api-packet"},
            )
            self.assertEqual(started.status_code, 201)
            self.assertEqual(started.json()["state"]["waiting_for"], "evidence_review")
            self.assertEqual(started.json()["job"]["job_mode"], "thesis_evolution_forecast")
        finally:
            routes.repository = original

    def test_role_prompts_preserve_frozen_authorities(self):
        root = Path(__file__).parents[1] / "config" / "prompt_templates"
        evolution = (root / "evolution_analyst_system.txt").read_text(encoding="utf-8")
        proposition = (root / "proposition_generator_system.txt").read_text(encoding="utf-8")
        reverse = (root / "reverse_reviewer_system.txt").read_text(encoding="utf-8")
        engineering = (root / "engineering_reviewer_system.txt").read_text(encoding="utf-8")
        adjudicator = (root / "adjudicator_system.txt").read_text(encoding="utf-8")
        reviser = (root / "claim_reviser_system.txt").read_text(encoding="utf-8")
        self.assertIn("null表示未知，不表示0", evolution)
        self.assertIn("不得增加历史记录、对象或证据ID", proposition)
        self.assertIn("不读取工程评审", reverse)
        self.assertIn("不读取反向审查", engineering)
        self.assertIn("不是角色数量或多数表决", adjudicator)
        self.assertIn("不修改冻结证据、对象ID、确定性模型概率或旧命题版本", reviser)


if __name__ == "__main__":
    unittest.main()
