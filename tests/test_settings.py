# -*- coding:utf-8-*-
import sys
import os
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _reload_settings():
    if "config.settings" in sys.modules:
        del sys.modules["config.settings"]
    return importlib.import_module("config.settings")


def test_existing_configs_preserved():
    settings = _reload_settings()
    assert hasattr(settings, "DEEPSEEK_API_KEY")
    assert hasattr(settings, "DEEPSEEK_BASE_URL")
    assert hasattr(settings, "DEEPSEEK_MODEL")
    assert hasattr(settings, "TEMPERATURE")
    assert hasattr(settings, "MAX_TOKENS")
    assert hasattr(settings, "REQUEST_TIMEOUT")
    assert hasattr(settings, "MAX_RETRIES")
    assert hasattr(settings, "ROOT_DIR")
    assert hasattr(settings, "DATA_RAW")
    assert isinstance(settings.TEMPERATURE, float)
    assert isinstance(settings.MAX_TOKENS, int)


def test_new_configs_exist():
    settings = _reload_settings()
    assert hasattr(settings, "ENABLE_SELF_CONSISTENCY")
    assert hasattr(settings, "ENABLE_MULTI_MODEL")
    assert hasattr(settings, "ENABLE_MULTI_AGENT_DEBATE")
    assert hasattr(settings, "ENABLE_REASONING_CHAIN")
    assert hasattr(settings, "SELF_CONSISTENCY_SAMPLES")
    assert hasattr(settings, "SELF_CONSISTENCY_TEMPERATURE_MIN")
    assert hasattr(settings, "SELF_CONSISTENCY_TEMPERATURE_MAX")
    assert hasattr(settings, "CONFIDENCE_THRESHOLD")
    assert hasattr(settings, "MULTI_MODEL_LIST")
    assert hasattr(settings, "MULTI_MODEL_STRATEGY")
    assert hasattr(settings, "DEBATE_ROUNDS")
    assert hasattr(settings, "DEBATE_AGENTS")
    assert hasattr(settings, "ENABLE_ROADMAP_ENHANCED")
    assert hasattr(settings, "BACKTEST_HISTORICAL_YEAR")


def test_default_values_backward_compatible():
    os.environ.pop("ENABLE_SELF_CONSISTENCY", None)
    os.environ.pop("ENABLE_MULTI_MODEL", None)
    os.environ.pop("ENABLE_MULTI_AGENT_DEBATE", None)
    os.environ.pop("ENABLE_REASONING_CHAIN", None)
    os.environ.pop("ENABLE_ROADMAP_ENHANCED", None)
    settings = _reload_settings()
    assert settings.ENABLE_SELF_CONSISTENCY is False
    assert settings.ENABLE_MULTI_MODEL is False
    assert settings.ENABLE_MULTI_AGENT_DEBATE is False
    assert settings.ENABLE_REASONING_CHAIN is False
    assert settings.ENABLE_ROADMAP_ENHANCED is False
    assert settings.SELF_CONSISTENCY_SAMPLES == 3
    assert settings.SELF_CONSISTENCY_TEMPERATURE_MIN == 0.1
    assert settings.SELF_CONSISTENCY_TEMPERATURE_MAX == 0.5
    assert settings.CONFIDENCE_THRESHOLD == 60
    assert settings.MULTI_MODEL_LIST == []
    assert settings.MULTI_MODEL_STRATEGY == "weighted_vote"
    assert settings.DEBATE_ROUNDS == 2
    assert settings.DEBATE_AGENTS == ["tech_expert", "industry_analyst", "risk_assessor"]
    assert settings.BACKTEST_HISTORICAL_YEAR == 2020


def test_config_types_correct():
    settings = _reload_settings()
    assert isinstance(settings.ENABLE_SELF_CONSISTENCY, bool)
    assert isinstance(settings.ENABLE_MULTI_MODEL, bool)
    assert isinstance(settings.ENABLE_MULTI_AGENT_DEBATE, bool)
    assert isinstance(settings.ENABLE_REASONING_CHAIN, bool)
    assert isinstance(settings.SELF_CONSISTENCY_SAMPLES, int)
    assert isinstance(settings.SELF_CONSISTENCY_TEMPERATURE_MIN, float)
    assert isinstance(settings.SELF_CONSISTENCY_TEMPERATURE_MAX, float)
    assert isinstance(settings.CONFIDENCE_THRESHOLD, int)
    assert isinstance(settings.MULTI_MODEL_LIST, list)
    assert isinstance(settings.MULTI_MODEL_STRATEGY, str)
    assert isinstance(settings.DEBATE_ROUNDS, int)
    assert isinstance(settings.DEBATE_AGENTS, list)
    assert isinstance(settings.ENABLE_ROADMAP_ENHANCED, bool)
    assert isinstance(settings.BACKTEST_HISTORICAL_YEAR, int)


def test_env_override_bool_true():
    os.environ["ENABLE_SELF_CONSISTENCY"] = "true"
    os.environ["ENABLE_MULTI_MODEL"] = "True"
    os.environ["ENABLE_MULTI_AGENT_DEBATE"] = "1"
    os.environ["ENABLE_REASONING_CHAIN"] = "yes"
    settings = _reload_settings()
    assert settings.ENABLE_SELF_CONSISTENCY is True
    assert settings.ENABLE_MULTI_MODEL is True
    assert settings.ENABLE_MULTI_AGENT_DEBATE is True
    assert settings.ENABLE_REASONING_CHAIN is True
    os.environ.pop("ENABLE_SELF_CONSISTENCY", None)
    os.environ.pop("ENABLE_MULTI_MODEL", None)
    os.environ.pop("ENABLE_MULTI_AGENT_DEBATE", None)
    os.environ.pop("ENABLE_REASONING_CHAIN", None)


def test_env_override_bool_false():
    os.environ["ENABLE_SELF_CONSISTENCY"] = "false"
    os.environ["ENABLE_MULTI_MODEL"] = "False"
    os.environ["ENABLE_MULTI_AGENT_DEBATE"] = "0"
    os.environ["ENABLE_REASONING_CHAIN"] = "no"
    settings = _reload_settings()
    assert settings.ENABLE_SELF_CONSISTENCY is False
    assert settings.ENABLE_MULTI_MODEL is False
    assert settings.ENABLE_MULTI_AGENT_DEBATE is False
    assert settings.ENABLE_REASONING_CHAIN is False
    os.environ.pop("ENABLE_SELF_CONSISTENCY", None)
    os.environ.pop("ENABLE_MULTI_MODEL", None)
    os.environ.pop("ENABLE_MULTI_AGENT_DEBATE", None)
    os.environ.pop("ENABLE_REASONING_CHAIN", None)


def test_env_override_int():
    os.environ["SELF_CONSISTENCY_SAMPLES"] = "5"
    os.environ["CONFIDENCE_THRESHOLD"] = "75"
    os.environ["DEBATE_ROUNDS"] = "3"
    os.environ["BACKTEST_HISTORICAL_YEAR"] = "2015"
    settings = _reload_settings()
    assert settings.SELF_CONSISTENCY_SAMPLES == 5
    assert settings.CONFIDENCE_THRESHOLD == 75
    assert settings.DEBATE_ROUNDS == 3
    assert settings.BACKTEST_HISTORICAL_YEAR == 2015
    os.environ.pop("SELF_CONSISTENCY_SAMPLES", None)
    os.environ.pop("CONFIDENCE_THRESHOLD", None)
    os.environ.pop("DEBATE_ROUNDS", None)
    os.environ.pop("BACKTEST_HISTORICAL_YEAR", None)


def test_env_override_float():
    os.environ["SELF_CONSISTENCY_TEMPERATURE_MIN"] = "0.2"
    os.environ["SELF_CONSISTENCY_TEMPERATURE_MAX"] = "0.8"
    settings = _reload_settings()
    assert settings.SELF_CONSISTENCY_TEMPERATURE_MIN == 0.2
    assert settings.SELF_CONSISTENCY_TEMPERATURE_MAX == 0.8
    os.environ.pop("SELF_CONSISTENCY_TEMPERATURE_MIN", None)
    os.environ.pop("SELF_CONSISTENCY_TEMPERATURE_MAX", None)


def test_env_override_json_list():
    os.environ["DEBATE_AGENTS"] = '["role1", "role2", "role3"]'
    settings = _reload_settings()
    assert settings.DEBATE_AGENTS == ["role1", "role2", "role3"]
    assert isinstance(settings.DEBATE_AGENTS, list)
    os.environ.pop("DEBATE_AGENTS", None)


def test_env_override_json_list_of_dicts():
    os.environ["MULTI_MODEL_LIST"] = '[{"name": "model1", "weight": 0.6}, {"name": "model2", "weight": 0.4}]'
    settings = _reload_settings()
    assert len(settings.MULTI_MODEL_LIST) == 2
    assert settings.MULTI_MODEL_LIST[0]["name"] == "model1"
    assert settings.MULTI_MODEL_LIST[0]["weight"] == 0.6
    assert settings.MULTI_MODEL_LIST[1]["name"] == "model2"
    os.environ.pop("MULTI_MODEL_LIST", None)


def test_env_override_json_empty_uses_default():
    os.environ["MULTI_MODEL_LIST"] = ""
    os.environ["DEBATE_AGENTS"] = ""
    settings = _reload_settings()
    assert settings.MULTI_MODEL_LIST == []
    assert settings.DEBATE_AGENTS == ["tech_expert", "industry_analyst", "risk_assessor"]
    os.environ.pop("MULTI_MODEL_LIST", None)
    os.environ.pop("DEBATE_AGENTS", None)


def test_env_override_json_invalid_uses_default():
    os.environ["MULTI_MODEL_LIST"] = "invalid json {{{"
    os.environ["DEBATE_AGENTS"] = "not json"
    settings = _reload_settings()
    assert settings.MULTI_MODEL_LIST == []
    assert settings.DEBATE_AGENTS == ["tech_expert", "industry_analyst", "risk_assessor"]
    os.environ.pop("MULTI_MODEL_LIST", None)
    os.environ.pop("DEBATE_AGENTS", None)


def test_env_override_string():
    os.environ["MULTI_MODEL_STRATEGY"] = "majority_vote"
    settings = _reload_settings()
    assert settings.MULTI_MODEL_STRATEGY == "majority_vote"
    os.environ.pop("MULTI_MODEL_STRATEGY", None)


def test_helper_functions_exist():
    settings = _reload_settings()
    assert hasattr(settings, "_str_to_bool")
    assert hasattr(settings, "_parse_json_env")
    assert callable(settings._str_to_bool)
    assert callable(settings._parse_json_env)


def run_all_tests():
    test_funcs = [
        test_existing_configs_preserved,
        test_new_configs_exist,
        test_default_values_backward_compatible,
        test_config_types_correct,
        test_env_override_bool_true,
        test_env_override_bool_false,
        test_env_override_int,
        test_env_override_float,
        test_env_override_json_list,
        test_env_override_json_list_of_dicts,
        test_env_override_json_empty_uses_default,
        test_env_override_json_invalid_uses_default,
        test_env_override_string,
        test_helper_functions_exist,
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
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
