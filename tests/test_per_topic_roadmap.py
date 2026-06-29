# -*- coding:utf-8 -*-
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.prompt_builder.per_topic_roadmap_builder import build_per_topic_roadmap_messages
from src.output_parser.parse_per_topic_roadmap import parse_per_topic_roadmap_output
from src.llm_orchestrator.per_topic_roadmap_runner import (
    _safe_filename,
    _run_single_roadmap,
    run_per_topic_roadmap,
    run_all_topics_roadmap,
)
from src.report.per_topic_roadmap_report import (
    generate_single_topic_report,
    generate_all_topics_report,
    save_per_topic_reports,
    _get_uncertainty_cn,
    _build_timeline,
    _build_flowchart,
)
from config import settings


SAMPLE_TOPIC_DATA = {
    "topic_name": "参数化与生成式设计",
    "bottlenecks_2030_2035": [
        "设计流程中多目标优化的实时协同计算能力不足",
        "AI算法与参数化模型的融合深度不足"
    ],
    "breakthroughs_by_2040": [
        "端到端生成式设计框架，实现从几何参数到性能仿真的闭环优化",
        "约束感知的生成式对抗网络，自动学习并满足建筑规范硬约束"
    ],
    "deep_fusion_topics": [
        "参数化与生成式设计",
        "建筑性能仿真与优化"
    ],
    "fusion_scenario": "建筑师输入场地条件与性能目标，融合系统自动生成数百个满足结构安全与规范约束的形态方案。",
    "typical_day_2040": "清晨，建筑师小陈在数字孪生平台上输入项目需求，AI助手30分钟内生成127个合规方案。"
}

SAMPLE_ROADMAP_JSON = {
    "2025": {
        "stage_description": "基础技术积累阶段，参数化设计工具逐步普及",
        "milestones": [
            {
                "name": "参数化设计工具普及",
                "description": "主流BIM软件全面集成参数化设计模块，设计师可通过可视化编程实现形态生成",
                "key_technologies": ["参数化建模", "BIM软件集成", "可视化编程"],
                "trl_level": 3,
                "dependencies": [],
                "uncertainty_level": "low"
            }
        ]
    },
    "2030": {
        "stage_description": "AI辅助设计突破阶段，生成式算法开始应用于概念设计",
        "milestones": [
            {
                "name": "生成式设计算法验证",
                "description": "基于遗传算法的多目标优化方案在试点项目中验证，可生成满足基本约束的建筑形态",
                "key_technologies": ["遗传算法", "多目标优化", "概念设计自动化"],
                "trl_level": 5,
                "dependencies": ["参数化设计工具普及"],
                "uncertainty_level": "medium"
            }
        ]
    },
    "2035": {
        "stage_description": "性能驱动设计阶段，AI与仿真深度融合",
        "milestones": [
            {
                "name": "性能仿真闭环优化",
                "description": "实现从几何参数到结构、能耗、采光等多物理场仿真的自动化迭代优化",
                "key_technologies": ["多物理场仿真", "AI驱动优化", "实时性能分析"],
                "trl_level": 7,
                "dependencies": ["生成式设计算法验证"],
                "uncertainty_level": "medium"
            }
        ]
    },
    "2040": {
        "stage_description": "自主设计范式阶段，端到端AI设计系统成熟应用",
        "milestones": [
            {
                "name": "端到端自主设计系统",
                "description": "基于大模型的生成式设计框架，自动学习规范约束，输入需求即可输出完整可施工方案",
                "key_technologies": ["建筑大模型", "约束感知GAN", "全流程自动化设计"],
                "trl_level": 9,
                "dependencies": ["性能仿真闭环优化"],
                "uncertainty_level": "high"
            }
        ]
    }
}


def test_build_messages_structure():
    messages = build_per_topic_roadmap_messages(SAMPLE_TOPIC_DATA)
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_build_messages_contains_topic_name():
    messages = build_per_topic_roadmap_messages(SAMPLE_TOPIC_DATA)
    user_content = messages[1]["content"]
    assert "参数化与生成式设计" in user_content


def test_build_messages_contains_bottlenecks():
    messages = build_per_topic_roadmap_messages(SAMPLE_TOPIC_DATA)
    user_content = messages[1]["content"]
    assert "多目标优化" in user_content
    assert "AI算法" in user_content


def test_build_messages_contains_breakthroughs():
    messages = build_per_topic_roadmap_messages(SAMPLE_TOPIC_DATA)
    user_content = messages[1]["content"]
    assert "端到端生成式设计框架" in user_content
    assert "约束感知" in user_content


def test_build_messages_contains_fusion_topics():
    messages = build_per_topic_roadmap_messages(SAMPLE_TOPIC_DATA)
    user_content = messages[1]["content"]
    assert "建筑性能仿真与优化" in user_content


def test_build_messages_empty_data():
    messages = build_per_topic_roadmap_messages({})
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_build_messages_topic_field_alias():
    data = {"topic": "机器人集群协同"}
    messages = build_per_topic_roadmap_messages(data)
    user_content = messages[1]["content"]
    assert "机器人集群协同" in user_content


def test_parse_pure_json():
    import json
    raw_text = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    result = parse_per_topic_roadmap_output(raw_text, "参数化与生成式设计")
    assert result["topic_name"] == "参数化与生成式设计"
    assert "2025" in result["roadmap"]
    assert "2030" in result["roadmap"]
    assert "2035" in result["roadmap"]
    assert "2040" in result["roadmap"]
    assert len(result["roadmap"]["2025"]["milestones"]) == 1


def test_parse_markdown_code_block():
    import json
    json_str = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    raw_text = f"以下是路线图分析结果：\n```json\n{json_str}\n```\n希望对您有帮助。"
    result = parse_per_topic_roadmap_output(raw_text, "测试主题")
    assert result["topic_name"] == "测试主题"
    assert len(result["roadmap"]) == 4
    assert result["roadmap"]["2040"]["milestones"][0]["trl_level"] == 9


def test_parse_with_prefix_suffix():
    import json
    json_str = json.dumps(SAMPLE_ROADMAP_JSON, ensure_ascii=False)
    raw_text = f"好的，我来为您生成技术路线图。\n{json_str}\n以上就是完整的路线图。"
    result = parse_per_topic_roadmap_output(raw_text, "参数化设计")
    assert result["topic_name"] == "参数化设计"
    assert "2025" in result["roadmap"]
    assert result["roadmap"]["2025"]["stage_description"] != ""


def test_parse_empty_input():
    result = parse_per_topic_roadmap_output("", "测试")
    assert result["topic_name"] == "测试"
    assert result["roadmap"] == {}


def test_parse_none_input():
    result = parse_per_topic_roadmap_output(None, "测试")
    assert result["topic_name"] == "测试"
    assert result["roadmap"] == {}


def test_parse_whitespace_only():
    result = parse_per_topic_roadmap_output("   \n\t  ", "测试")
    assert result["roadmap"] == {}


def test_parse_invalid_json():
    raw_text = "这不是一个有效的JSON {{{"
    result = parse_per_topic_roadmap_output(raw_text, "测试")
    assert result["roadmap"] == {}


def test_parse_milestone_fields():
    import json
    raw_text = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    result = parse_per_topic_roadmap_output(raw_text, "测试")
    milestone = result["roadmap"]["2030"]["milestones"][0]
    assert "name" in milestone
    assert "description" in milestone
    assert "key_technologies" in milestone
    assert "trl_level" in milestone
    assert "dependencies" in milestone
    assert "uncertainty_level" in milestone
    assert isinstance(milestone["key_technologies"], list)
    assert isinstance(milestone["dependencies"], list)
    assert isinstance(milestone["trl_level"], int)
    assert 1 <= milestone["trl_level"] <= 9
    assert milestone["uncertainty_level"] in ("low", "medium", "high")


def test_parse_chinese_field_names():
    raw_text = '''
    {
        "技术路线图": {
            "2025": {
                "阶段描述": "基础阶段",
                "里程碑": [
                    {
                        "名称": "技术起步",
                        "描述": "开始基础研究",
                        "关键技术": ["基础算法"],
                        "TRL等级": 2,
                        "依赖": [],
                        "不确定性等级": "低"
                    }
                ]
            }
        }
    }
    '''
    result = parse_per_topic_roadmap_output(raw_text, "测试主题")
    assert "2025" in result["roadmap"]
    assert result["roadmap"]["2025"]["stage_description"] == "基础阶段"
    ms = result["roadmap"]["2025"]["milestones"][0]
    assert ms["name"] == "技术起步"
    assert ms["trl_level"] == 2
    assert ms["uncertainty_level"] == "low"


def test_parse_uncertainty_chinese_mapping():
    raw_text = '''
    {
        "roadmap": {
            "2030": {
                "stage_description": "测试",
                "milestones": [
                    {"name": "A", "description": "desc", "key_technologies": [], "trl_level": 5, "dependencies": [], "uncertainty_level": "高"},
                    {"name": "B", "description": "desc", "key_technologies": [], "trl_level": 5, "dependencies": [], "uncertainty_level": "中"},
                    {"name": "C", "description": "desc", "key_technologies": [], "trl_level": 5, "dependencies": [], "uncertainty_level": "低"}
                ]
            }
        }
    }
    '''
    result = parse_per_topic_roadmap_output(raw_text, "测试")
    milestones = result["roadmap"]["2030"]["milestones"]
    assert milestones[0]["uncertainty_level"] == "high"
    assert milestones[1]["uncertainty_level"] == "medium"
    assert milestones[2]["uncertainty_level"] == "low"


def test_parse_invalid_trl_level():
    raw_text = '''
    {
        "roadmap": {
            "2030": {
                "stage_description": "测试",
                "milestones": [
                    {"name": "A", "description": "desc", "key_technologies": [], "trl_level": 15, "dependencies": [], "uncertainty_level": "low"},
                    {"name": "B", "description": "desc", "key_technologies": [], "trl_level": 0, "dependencies": [], "uncertainty_level": "low"}
                ]
            }
        }
    }
    '''
    result = parse_per_topic_roadmap_output(raw_text, "测试")
    milestones = result["roadmap"]["2030"]["milestones"]
    assert milestones[0]["trl_level"] is None
    assert milestones[1]["trl_level"] is None


def test_parse_default_topic_name():
    import json
    raw_text = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    result = parse_per_topic_roadmap_output(raw_text)
    assert result["topic_name"] == ""


def test_parse_roadmap_at_root_level():
    import json
    raw_text = json.dumps(SAMPLE_ROADMAP_JSON, ensure_ascii=False)
    result = parse_per_topic_roadmap_output(raw_text, "测试")
    assert "2025" in result["roadmap"]
    assert "2030" in result["roadmap"]


class MockLLMClient:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.called_messages = []
        self.called_temperatures = []

    def chat_completion(self, messages, temperature=None, max_tokens=None):
        self.called_messages.append(messages)
        self.called_temperatures.append(temperature)
        idx = self.call_count
        self.call_count += 1
        if idx < len(self.responses):
            return self.responses[idx]
        return self.responses[-1] if self.responses else None


def test_safe_filename_chinese():
    assert _safe_filename("参数化与生成式设计") == "参数化与生成式设计"


def test_safe_filename_with_spaces():
    assert _safe_filename("建筑 机器人 技术") == "建筑_机器人_技术"


def test_safe_filename_special_chars():
    assert _safe_filename('test/filename:with*special?chars<>|') == "test_filename_with_special_chars"


def test_safe_filename_mixed():
    assert _safe_filename("智能建造/AI 技术: 2040") == "智能建造_AI_技术_2040"


def test_safe_filename_empty():
    assert _safe_filename("") == "unnamed"


def test_safe_filename_none_like():
    assert _safe_filename("___") == "unnamed"


def test_safe_filename_leading_trailing_underscore():
    assert _safe_filename("_test_name_") == "test_name"


def _make_sample_roadmap_response(topic_name="测试主题"):
    return json.dumps({"roadmap": SAMPLE_ROADMAP_JSON, "topic_name": topic_name}, ensure_ascii=False)


def test_run_single_roadmap_success():
    response = _make_sample_roadmap_response()
    mock_client = MockLLMClient([response])
    result = _run_single_roadmap(mock_client, SAMPLE_TOPIC_DATA)
    assert result is not None
    assert "roadmap" in result
    assert len(result["roadmap"]) == 4
    assert mock_client.call_count == 1


def test_run_single_roadmap_api_failure():
    mock_client = MockLLMClient([None])
    result = _run_single_roadmap(mock_client, SAMPLE_TOPIC_DATA)
    assert result == {}


def test_run_single_roadmap_invalid_response():
    mock_client = MockLLMClient(["不是有效的json"])
    result = _run_single_roadmap(mock_client, SAMPLE_TOPIC_DATA)
    assert result == {}


def test_run_per_topic_roadmap_caching():
    import shutil
    from pathlib import Path
    from src.llm_orchestrator import per_topic_roadmap_runner as runner_module

    temp_dir = tempfile.mkdtemp()
    try:
        response = _make_sample_roadmap_response()
        mock_client = MockLLMClient([response, response])

        orig_es = runner_module.ENABLE_SELF_CONSISTENCY
        orig_em = runner_module.ENABLE_MULTI_MODEL
        orig_ed = runner_module.ENABLE_MULTI_AGENT_DEBATE
        orig_ml = runner_module.MULTI_MODEL_LIST
        orig_llm = runner_module.LLMClient
        orig_parsed = runner_module.OUTPUTS_PARSED

        runner_module.ENABLE_SELF_CONSISTENCY = False
        runner_module.ENABLE_MULTI_MODEL = False
        runner_module.ENABLE_MULTI_AGENT_DEBATE = False
        runner_module.MULTI_MODEL_LIST = []
        runner_module.OUTPUTS_PARSED = Path(temp_dir)

        call_counter = {'count': 0}
        def mock_llm_client_factory(*args, **kwargs):
            call_counter['count'] += 1
            return mock_client

        runner_module.LLMClient = mock_llm_client_factory

        try:
            result1 = run_per_topic_roadmap(SAMPLE_TOPIC_DATA, force_rerun=False)
            assert mock_client.call_count == 1
            assert result1.get("roadmap") is not None

            result2 = run_per_topic_roadmap(SAMPLE_TOPIC_DATA, force_rerun=False)
            assert mock_client.call_count == 1
            assert result2.get("roadmap") is not None
        finally:
            runner_module.ENABLE_SELF_CONSISTENCY = orig_es
            runner_module.ENABLE_MULTI_MODEL = orig_em
            runner_module.ENABLE_MULTI_AGENT_DEBATE = orig_ed
            runner_module.MULTI_MODEL_LIST = orig_ml
            runner_module.LLMClient = orig_llm
            runner_module.OUTPUTS_PARSED = orig_parsed
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_run_per_topic_roadmap_force_rerun():
    response = _make_sample_roadmap_response()
    mock_client = MockLLMClient([response, response])

    with patch('src.llm_orchestrator.per_topic_roadmap_runner.LLMClient', return_value=mock_client):
        with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_SELF_CONSISTENCY', False):
            with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_AGENT_DEBATE', False):
                with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_MODEL', False):
                    with patch('src.llm_orchestrator.per_topic_roadmap_runner.MULTI_MODEL_LIST', []):
                        with patch('src.llm_orchestrator.per_topic_roadmap_runner.write_json'):
                            with patch('src.llm_orchestrator.per_topic_roadmap_runner.read_json') as mock_read:
                                cached = {"topic_name": "缓存数据", "roadmap": {"2025": {}}}
                                mock_read.return_value = cached

                                result = run_per_topic_roadmap(SAMPLE_TOPIC_DATA, force_rerun=True)
                                assert mock_client.call_count == 1
                                assert result["topic_name"] == "参数化与生成式设计"


def test_run_all_topics_roadmap_success():
    topics = [
        {"topic_name": "主题A", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
        {"topic_name": "主题B", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
        {"topic_name": "主题C", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
    ]
    response = _make_sample_roadmap_response()
    mock_client = MockLLMClient([response, response, response])

    with patch('src.llm_orchestrator.per_topic_roadmap_runner.LLMClient', return_value=mock_client):
        with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_SELF_CONSISTENCY', False):
            with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_AGENT_DEBATE', False):
                with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_MODEL', False):
                    with patch('src.llm_orchestrator.per_topic_roadmap_runner.MULTI_MODEL_LIST', []):
                        with patch('src.llm_orchestrator.per_topic_roadmap_runner.write_json'):
                            with patch('src.llm_orchestrator.per_topic_roadmap_runner.read_json', return_value=None):
                                results = run_all_topics_roadmap(topics, force_rerun=True)
                                assert len(results) == 3
                                assert mock_client.call_count == 3


def test_run_all_topics_roadmap_single_failure():
    topics = [
        {"topic_name": "成功主题", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
        {"topic_name": "失败主题", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
        {"topic_name": "成功主题2", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
    ]

    class FailingMockClient:
        def __init__(self):
            self.call_count = 0

        def chat_completion(self, messages, temperature=None, max_tokens=None):
            self.call_count += 1
            if self.call_count == 2:
                raise RuntimeError("模拟API异常")
            return _make_sample_roadmap_response()

    mock_client = FailingMockClient()

    with patch('src.llm_orchestrator.per_topic_roadmap_runner.LLMClient', return_value=mock_client):
        with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_SELF_CONSISTENCY', False):
            with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_AGENT_DEBATE', False):
                with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_MODEL', False):
                    with patch('src.llm_orchestrator.per_topic_roadmap_runner.MULTI_MODEL_LIST', []):
                        with patch('src.llm_orchestrator.per_topic_roadmap_runner.write_json'):
                            with patch('src.llm_orchestrator.per_topic_roadmap_runner.read_json', return_value=None):
                                results = run_all_topics_roadmap(topics, force_rerun=True)
                                assert len(results) == 2
                                assert mock_client.call_count == 3


def test_run_all_topics_roadmap_empty_input():
    with patch('src.llm_orchestrator.per_topic_roadmap_runner.write_json'):
        results = run_all_topics_roadmap([], force_rerun=True)
        assert results == []


def test_self_consistency_compatibility():
    from src.llm_orchestrator.per_topic_roadmap_runner import _run_self_consistency_roadmap
    response = _make_sample_roadmap_response()
    mock_client = MockLLMClient([response, response, response])

    result = _run_self_consistency_roadmap(mock_client, SAMPLE_TOPIC_DATA)
    assert result is not None
    assert result.get("success") is True
    assert "confidence" in result
    assert mock_client.call_count == 3


def test_debate_compatibility():
    from src.llm_orchestrator.per_topic_roadmap_runner import _run_debate_roadmap

    review_response = """【优点】
- 结构完整

【主要问题】
- 细节不足

【改进建议】
- 补充细节"""

    revision_response = _make_sample_roadmap_response()
    summary_response = "辩论摘要"

    initial_response = _make_sample_roadmap_response()

    mock_client = MockLLMClient([
        initial_response,
        review_response,
        review_response,
        review_response,
        revision_response,
        review_response,
        review_response,
        review_response,
        summary_response,
    ])

    with patch('src.llm_orchestrator.per_topic_roadmap_runner.DEBATE_AGENTS', ["tech_expert"]):
        with patch('src.llm_orchestrator.per_topic_roadmap_runner.DEBATE_ROUNDS', 2):
            result = _run_debate_roadmap(mock_client, SAMPLE_TOPIC_DATA)
            assert result is not None
            assert "debate_info" in result
            assert result["debate_info"].get("success") is True


def test_multi_model_compatibility():
    from src.llm_orchestrator.per_topic_roadmap_runner import _run_multi_model_roadmap

    class MockMultiClient:
        def chat_completion(self, messages, temperature=None, max_tokens=None):
            return {
                "results": [
                    {"model_name": "model_a", "content": _make_sample_roadmap_response(), "success": True},
                    {"model_name": "model_b", "content": _make_sample_roadmap_response(), "success": True},
                ],
                "model_count": 2
            }

        def get_normalized_weights(self, active_models=None):
            count = len(active_models) if active_models else 2
            return {name: 1.0 / count for name in (active_models or ["model_a", "model_b"])}

    mock_multi = MockMultiClient()
    result = _run_multi_model_roadmap(mock_multi, SAMPLE_TOPIC_DATA)
    assert result is not None
    assert result.get("success") is True
    assert "num_models" in result
    assert result["num_models"] == 2


def test_settings_per_topic_roadmap():
    assert hasattr(settings, 'ENABLE_PER_TOPIC_ROADMAP')
    assert isinstance(settings.ENABLE_PER_TOPIC_ROADMAP, bool)
    assert hasattr(settings, 'PER_TOPIC_ROADMAP_STAGES')
    assert isinstance(settings.PER_TOPIC_ROADMAP_STAGES, list)
    assert len(settings.PER_TOPIC_ROADMAP_STAGES) == 4
    assert "2025" in settings.PER_TOPIC_ROADMAP_STAGES


SAMPLE_ROADMAP_DATA = {
    "topic_name": "参数化与生成式设计",
    "roadmap": SAMPLE_ROADMAP_JSON
}


def test_uncertainty_cn_mapping():
    assert _get_uncertainty_cn("low") == "低"
    assert _get_uncertainty_cn("medium") == "中"
    assert _get_uncertainty_cn("high") == "高"
    assert _get_uncertainty_cn("unknown") == "unknown"


def test_single_topic_report_contains_title():
    report = generate_single_topic_report(SAMPLE_ROADMAP_DATA)
    assert "# 参数化与生成式设计" in report


def test_single_topic_report_contains_timeline():
    report = generate_single_topic_report(SAMPLE_ROADMAP_DATA)
    assert "## 时间轴视图" in report
    assert "```mermaid" in report
    assert "timeline" in report


def test_single_topic_report_contains_flowchart():
    report = generate_single_topic_report(SAMPLE_ROADMAP_DATA)
    assert "## 流程图视图" in report
    assert "flowchart TD" in report


def test_single_topic_report_contains_tables():
    report = generate_single_topic_report(SAMPLE_ROADMAP_DATA)
    assert "## 分阶段详细里程碑" in report
    assert "| 里程碑 | 描述 | 关键技术 | TRL等级 | 不确定性 | 依赖 |" in report


def test_single_topic_report_contains_statistics():
    report = generate_single_topic_report(SAMPLE_ROADMAP_DATA)
    assert "统计信息" in report
    assert "总里程碑数量" in report
    assert "各阶段里程碑数量" in report


def test_mermaid_timeline_syntax():
    timeline = _build_timeline(SAMPLE_ROADMAP_DATA, "测试主题")
    assert timeline.startswith("```mermaid")
    assert "timeline" in timeline
    assert "title 测试主题 技术发展路线图" in timeline
    assert "2025" in timeline
    assert "2030" in timeline
    assert "2035" in timeline
    assert "2040" in timeline
    assert timeline.strip().endswith("```")


def test_mermaid_timeline_contains_milestones():
    timeline = _build_timeline(SAMPLE_ROADMAP_DATA, "参数化与生成式设计")
    assert "参数化设计工具普及" in timeline
    assert "生成式设计算法验证" in timeline
    assert "性能仿真闭环优化" in timeline
    assert "端到端自主设计系统" in timeline


def test_mermaid_flowchart_syntax():
    flowchart = _build_flowchart(SAMPLE_ROADMAP_DATA)
    assert flowchart.startswith("```mermaid")
    assert "flowchart TD" in flowchart
    assert "subgraph" in flowchart
    assert "2025年" in flowchart
    assert "2030年" in flowchart
    assert flowchart.strip().endswith("```")


def test_mermaid_flowchart_contains_nodes():
    flowchart = _build_flowchart(SAMPLE_ROADMAP_DATA)
    assert "参数化设计工具普及" in flowchart
    assert "生成式设计算法验证" in flowchart
    assert "TRL-3" in flowchart
    assert "TRL-5" in flowchart
    assert "TRL-9" in flowchart


def test_mermaid_flowchart_dependencies():
    flowchart = _build_flowchart(SAMPLE_ROADMAP_DATA)
    assert "-->" in flowchart


def test_all_topics_report_contains_title():
    roadmaps = [SAMPLE_ROADMAP_DATA]
    report = generate_all_topics_report(roadmaps)
    assert "# 智能建造2040 - 分主题技术路线图" in report
    assert "生成时间" in report


def test_all_topics_report_contains_index():
    roadmaps = [
        {"topic_name": "主题A", "roadmap": SAMPLE_ROADMAP_JSON},
        {"topic_name": "主题B", "roadmap": SAMPLE_ROADMAP_JSON},
    ]
    report = generate_all_topics_report(roadmaps)
    assert "## 目录" in report
    assert "主题A" in report
    assert "主题B" in report


def test_all_topics_report_contains_statistics_summary():
    roadmaps = [
        {"topic_name": "主题A", "roadmap": SAMPLE_ROADMAP_JSON},
        {"topic_name": "主题B", "roadmap": SAMPLE_ROADMAP_JSON},
    ]
    report = generate_all_topics_report(roadmaps)
    assert "统计汇总" in report
    assert "总主题数" in report
    assert "总里程碑数" in report
    assert "2" in report


def test_all_topics_report_contains_all_topics():
    roadmaps = [
        {"topic_name": "主题A", "roadmap": SAMPLE_ROADMAP_JSON},
        {"topic_name": "主题B", "roadmap": SAMPLE_ROADMAP_JSON},
    ]
    report = generate_all_topics_report(roadmaps)
    assert "# 主题A" in report
    assert "# 主题B" in report


@patch('src.report.per_topic_roadmap_report.write_text')
@patch('src.report.per_topic_roadmap_report.OUTPUTS_REPORT')
def test_save_per_topic_reports(mock_outputs, mock_write):
    from pathlib import Path
    mock_outputs.__truediv__.side_effect = lambda x: Path(f"/tmp/test_output/{x}")

    roadmaps = [
        {"topic_name": "主题A", "roadmap": SAMPLE_ROADMAP_JSON},
        {"topic_name": "主题B", "roadmap": SAMPLE_ROADMAP_JSON},
    ]

    all_path, single_paths = save_per_topic_reports(roadmaps)

    assert mock_write.called
    assert len(single_paths) == 2
    assert "per_topic_roadmaps_all.md" in str(all_path)


def test_empty_roadmap_data():
    empty_data = {"topic_name": "空主题", "roadmap": {}}
    report = generate_single_topic_report(empty_data)
    assert "# 空主题" in report
    assert "总里程碑数量" in report
    assert "0" in report


def test_partial_milestone_fields():
    partial_data = {
        "topic_name": "部分字段测试",
        "roadmap": {
            "2025": {
                "stage_description": "测试阶段",
                "milestones": [
                    {
                        "name": "测试里程碑",
                        "description": "",
                        "key_technologies": [],
                        "trl_level": None,
                        "dependencies": [],
                        "uncertainty_level": "medium"
                    }
                ]
            }
        }
    }
    report = generate_single_topic_report(partial_data)
    assert "# 部分字段测试" in report
    assert "测试里程碑" in report
    assert "TRL-?" not in report
    assert "中" in report


def test_milestone_without_dependencies_default_connection():
    data = {
        "topic_name": "无依赖测试",
        "roadmap": {
            "2025": {
                "stage_description": "",
                "milestones": [
                    {"name": "里程碑A", "description": "desc", "key_technologies": [], "trl_level": 2, "dependencies": [], "uncertainty_level": "low"}
                ]
            },
            "2030": {
                "stage_description": "",
                "milestones": [
                    {"name": "里程碑B", "description": "desc", "key_technologies": [], "trl_level": 4, "dependencies": [], "uncertainty_level": "low"}
                ]
            }
        }
    }
    flowchart = _build_flowchart(data)
    assert "-->" in flowchart


def test_stage_description_in_overview():
    report = generate_single_topic_report(SAMPLE_ROADMAP_DATA)
    assert "概述" in report
    assert "基础技术积累阶段" in report


def test_end_to_end_single_topic():
    """端到端测试：构建消息 → 调用LLM → 解析结果 → 生成报告"""
    import json

    messages = build_per_topic_roadmap_messages(SAMPLE_TOPIC_DATA)
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "参数化与生成式设计" in messages[1]["content"]

    response = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    parsed = parse_per_topic_roadmap_output(response, "参数化与生成式设计")
    assert parsed["topic_name"] == "参数化与生成式设计"
    assert "roadmap" in parsed
    assert len(parsed["roadmap"]) == 4
    assert "2025" in parsed["roadmap"]
    assert "2040" in parsed["roadmap"]

    report = generate_single_topic_report(parsed)
    assert "# 参数化与生成式设计" in report
    assert "时间轴视图" in report
    assert "流程图视图" in report
    assert "分阶段详细里程碑" in report
    assert "统计信息" in report


NINE_TOPICS = [
    "参数化与生成式设计",
    "建筑工程大模型技术",
    "施工全过程数字孪生",
    "建筑规模增材制造",
    "机器人集群协同",
    "模块化与可重构设计",
    "装配式建筑技术",
    "智能规范审查",
    "多专业协同平台",
]


def test_end_to_end_all_nine_topics():
    """测试所有9个主题的批量处理"""
    import json

    topics = []
    for name in NINE_TOPICS:
        topics.append({
            "topic_name": name,
            "bottlenecks_2030_2035": [f"{name}瓶颈1", f"{name}瓶颈2"],
            "breakthroughs_by_2040": [f"{name}突破1", f"{name}突破2"],
            "deep_fusion_topics": [f"{name}融合1"],
            "fusion_scenario": f"{name}的融合场景",
            "typical_day_2040": f"{name}的典型一天",
        })

    response = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    mock_client = MockLLMClient([response] * 9)

    with patch('src.llm_orchestrator.per_topic_roadmap_runner.LLMClient', return_value=mock_client):
        with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_SELF_CONSISTENCY', False):
            with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_AGENT_DEBATE', False):
                with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_MODEL', False):
                    with patch('src.llm_orchestrator.per_topic_roadmap_runner.MULTI_MODEL_LIST', []):
                        with patch('src.llm_orchestrator.per_topic_roadmap_runner.write_json'):
                            with patch('src.llm_orchestrator.per_topic_roadmap_runner.read_json', return_value=None):
                                results = run_all_topics_roadmap(topics, force_rerun=True)
                                assert len(results) == 9
                                assert mock_client.call_count == 9

    for i, result in enumerate(results):
        assert "topic_name" in result
        assert "roadmap" in result
        assert len(result["roadmap"]) == 4

    all_report = generate_all_topics_report(results)
    assert "# 智能建造2040 - 分主题技术路线图" in all_report
    assert "统计汇总" in all_report
    assert "9" in all_report
    for topic_name in NINE_TOPICS:
        assert topic_name in all_report


def test_self_consistency_end_to_end():
    """测试与自洽性功能的兼容性"""
    from src.llm_orchestrator.per_topic_roadmap_runner import _run_self_consistency_roadmap
    import json

    response = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    mock_client = MockLLMClient([response, response, response])

    result = _run_self_consistency_roadmap(mock_client, SAMPLE_TOPIC_DATA)
    assert result is not None
    assert result.get("success") is True
    assert "confidence" in result
    assert "roadmap" in result
    assert mock_client.call_count == 3

    report = generate_single_topic_report(result)
    assert "# 参数化与生成式设计" in report


def test_debate_end_to_end():
    """测试与辩论功能的兼容性"""
    from src.llm_orchestrator.per_topic_roadmap_runner import _run_debate_roadmap
    import json

    review_response = """【优点】
- 结构完整
- 时间节点合理

【主要问题】
- 部分细节可进一步完善

【改进建议】
- 补充关键技术细节"""

    revision_response = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
    summary_response = "经过多轮辩论，专家们对技术路线图达成了基本共识..."

    initial_response = json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)

    mock_client = MockLLMClient([
        initial_response,
        review_response,
        review_response,
        review_response,
        revision_response,
        review_response,
        review_response,
        review_response,
        summary_response,
    ])

    with patch('src.llm_orchestrator.per_topic_roadmap_runner.DEBATE_AGENTS', ["tech_expert"]):
        with patch('src.llm_orchestrator.per_topic_roadmap_runner.DEBATE_ROUNDS', 2):
            result = _run_debate_roadmap(mock_client, SAMPLE_TOPIC_DATA)
            assert result is not None
            assert "debate_info" in result
            assert result["debate_info"].get("success") is True
            assert "roadmap" in result

    report = generate_single_topic_report(result)
    assert "# 参数化与生成式设计" in report


def test_multi_model_end_to_end():
    """测试与多模型集成功能的兼容性"""
    from src.llm_orchestrator.per_topic_roadmap_runner import _run_multi_model_roadmap
    import json

    class MockMultiClient:
        def chat_completion(self, messages, temperature=None, max_tokens=None):
            return {
                "results": [
                    {"model_name": "model_a", "content": json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False), "success": True},
                    {"model_name": "model_b", "content": json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False), "success": True},
                    {"model_name": "model_c", "content": json.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False), "success": True},
                ],
                "model_count": 3
            }

        def get_normalized_weights(self, active_models=None):
            count = len(active_models) if active_models else 3
            return {name: 1.0 / count for name in (active_models or ["model_a", "model_b", "model_c"])}

    mock_multi = MockMultiClient()
    result = _run_multi_model_roadmap(mock_multi, SAMPLE_TOPIC_DATA)
    assert result is not None
    assert result.get("success") is True
    assert "num_models" in result
    assert result["num_models"] == 3
    assert "roadmap" in result


def test_config_switch_disabled():
    """测试 ENABLE_PER_TOPIC_ROADMAP=False 时主流程不受影响"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"
        mock_outputs_report.mkdir(parents=True, exist_ok=True)

        mock_round1 = [{"topic_name": "测试主题", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []}]
        mock_round2 = {"new_paradigm_name": "测试范式", "new_paradigm_description": "测试描述"}
        mock_round3 = []

        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            from src.report_generator import generate_final_report
            generate_final_report(mock_round1, mock_round2, mock_round3, roadmaps=[])

        report_path = mock_outputs_report / "forecast_report.md"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "智能建造2040技术趋势预测报告" in content
        assert "分主题技术路线图" not in content


def test_config_switch_enabled():
    """测试 ENABLE_PER_TOPIC_ROADMAP=True 时主流程正确调用"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"
        mock_outputs_report.mkdir(parents=True, exist_ok=True)

        mock_round1 = [{"topic_name": "测试主题", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []}]
        mock_round2 = {"new_paradigm_name": "测试范式", "new_paradigm_description": "测试描述"}
        mock_round3 = []

        roadmaps = [
            {"topic_name": "测试主题", "roadmap": SAMPLE_ROADMAP_JSON}
        ]

        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            from src.report_generator import generate_final_report
            generate_final_report(mock_round1, mock_round2, mock_round3, roadmaps=roadmaps)

        report_path = mock_outputs_report / "forecast_report.md"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "智能建造2040技术趋势预测报告" in content
        assert "分主题技术路线图" in content
        assert "测试主题" in content
        assert "per_topic_roadmaps" in content


def test_main_integration_with_roadmaps():
    """测试主流程集成（直接测试generate_final_report的分主题路线图章节）"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_outputs_report = tmp_path / "outputs" / "final_report"
        mock_outputs_report.mkdir(parents=True, exist_ok=True)

        mock_round1 = [
            {"topic_name": "建筑机器人", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []},
            {"topic_name": "数字孪生", "bottlenecks_2030_2035": [], "breakthroughs_by_2040": []}
        ]
        mock_round2 = {"new_paradigm_name": "测试范式", "new_paradigm_description": "测试描述"}
        mock_round3 = []

        roadmaps = [
            {"topic_name": "建筑机器人", "roadmap": SAMPLE_ROADMAP_JSON},
            {"topic_name": "数字孪生", "roadmap": SAMPLE_ROADMAP_JSON}
        ]

        with patch('src.report_generator.OUTPUTS_REPORT', mock_outputs_report):
            from src.report_generator import generate_final_report
            generate_final_report(mock_round1, mock_round2, mock_round3, roadmaps=roadmaps)

        report_path = mock_outputs_report / "forecast_report.md"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "智能建造2040技术趋势预测报告" in content
        assert "分主题技术路线图" in content
        assert "建筑机器人" in content
        assert "数字孪生" in content


def test_cached_data_reading():
    """测试使用缓存数据读取第一轮结果并生成路线图（使用mock API）"""
    import tempfile
    import json
    from pathlib import Path
    from src.utils.file_io import write_json, read_json

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mock_parsed = tmp_path / "parsed"
        mock_parsed.mkdir(parents=True, exist_ok=True)

        cached_topics = [
            {"topic_name": "主题A", "bottlenecks_2030_2035": ["b1"], "breakthroughs_by_2040": ["br1"]},
            {"topic_name": "主题B", "bottlenecks_2030_2035": ["b2"], "breakthroughs_by_2040": ["br2"]},
            {"topic_name": "主题C", "bottlenecks_2030_2035": ["b3"], "breakthroughs_by_2040": ["br3"]},
        ]

        for i, topic in enumerate(cached_topics):
            write_json(topic, mock_parsed / f"round1_主题{i+1}.json")

        round1_files = sorted(mock_parsed.glob("round1_*.json"))
        assert len(round1_files) == 3

        loaded_results = []
        for f in round1_files:
            data = read_json(f)
            if data:
                loaded_results.append(data)
        assert len(loaded_results) == 3

        import json as json_mod
        response = json_mod.dumps({"roadmap": SAMPLE_ROADMAP_JSON}, ensure_ascii=False)
        mock_client = MockLLMClient([response] * 3)

        with patch('src.llm_orchestrator.per_topic_roadmap_runner.LLMClient', return_value=mock_client):
            with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_SELF_CONSISTENCY', False):
                with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_AGENT_DEBATE', False):
                    with patch('src.llm_orchestrator.per_topic_roadmap_runner.ENABLE_MULTI_MODEL', False):
                        with patch('src.llm_orchestrator.per_topic_roadmap_runner.MULTI_MODEL_LIST', []):
                            with patch('src.llm_orchestrator.per_topic_roadmap_runner.OUTPUTS_PARSED', mock_parsed):
                                with patch('src.llm_orchestrator.per_topic_roadmap_runner.read_json', return_value=None):
                                    results = run_all_topics_roadmap(loaded_results, force_rerun=True)
                                    assert len(results) == 3
                                    assert mock_client.call_count == 3

        for result in results:
            assert "roadmap" in result
            assert len(result["roadmap"]) == 4


def run_all_tests():
    test_funcs = [
        test_build_messages_structure,
        test_build_messages_contains_topic_name,
        test_build_messages_contains_bottlenecks,
        test_build_messages_contains_breakthroughs,
        test_build_messages_contains_fusion_topics,
        test_build_messages_empty_data,
        test_build_messages_topic_field_alias,
        test_parse_pure_json,
        test_parse_markdown_code_block,
        test_parse_with_prefix_suffix,
        test_parse_empty_input,
        test_parse_none_input,
        test_parse_whitespace_only,
        test_parse_invalid_json,
        test_parse_milestone_fields,
        test_parse_chinese_field_names,
        test_parse_uncertainty_chinese_mapping,
        test_parse_invalid_trl_level,
        test_parse_default_topic_name,
        test_parse_roadmap_at_root_level,
        test_safe_filename_chinese,
        test_safe_filename_with_spaces,
        test_safe_filename_special_chars,
        test_safe_filename_mixed,
        test_safe_filename_empty,
        test_safe_filename_none_like,
        test_safe_filename_leading_trailing_underscore,
        test_run_single_roadmap_success,
        test_run_single_roadmap_api_failure,
        test_run_single_roadmap_invalid_response,
        test_run_per_topic_roadmap_caching,
        test_run_per_topic_roadmap_force_rerun,
        test_run_all_topics_roadmap_success,
        test_run_all_topics_roadmap_single_failure,
        test_run_all_topics_roadmap_empty_input,
        test_self_consistency_compatibility,
        test_debate_compatibility,
        test_multi_model_compatibility,
        test_settings_per_topic_roadmap,
        test_uncertainty_cn_mapping,
        test_single_topic_report_contains_title,
        test_single_topic_report_contains_timeline,
        test_single_topic_report_contains_flowchart,
        test_single_topic_report_contains_tables,
        test_single_topic_report_contains_statistics,
        test_mermaid_timeline_syntax,
        test_mermaid_timeline_contains_milestones,
        test_mermaid_flowchart_syntax,
        test_mermaid_flowchart_contains_nodes,
        test_mermaid_flowchart_dependencies,
        test_all_topics_report_contains_title,
        test_all_topics_report_contains_index,
        test_all_topics_report_contains_statistics_summary,
        test_all_topics_report_contains_all_topics,
        test_save_per_topic_reports,
        test_empty_roadmap_data,
        test_partial_milestone_fields,
        test_milestone_without_dependencies_default_connection,
        test_stage_description_in_overview,
        test_end_to_end_single_topic,
        test_end_to_end_all_nine_topics,
        test_self_consistency_end_to_end,
        test_debate_end_to_end,
        test_multi_model_end_to_end,
        test_config_switch_disabled,
        test_config_switch_enabled,
        test_main_integration_with_roadmaps,
        test_cached_data_reading,
    ]

    passed = 0
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"✓ {func.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
