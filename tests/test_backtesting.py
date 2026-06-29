# -*- coding:utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.backtesting import (
    Backtester,
    generate_mock_historical_data,
    calculate_metrics,
    generate_report,
)


def test_backtester_init_default():
    backtester = Backtester()
    assert backtester.historical_data is None
    assert backtester.results is None


def test_backtester_init_with_data():
    test_data = {"year": 2020, "topics": [], "emerged_technologies": []}
    backtester = Backtester(historical_data=test_data)
    assert backtester.historical_data == test_data
    assert backtester.results is None


def test_generate_mock_historical_data_same_year():
    base_topics = [
        {"name": "技术A", "keywords": ["a"]},
        {"name": "技术B", "keywords": ["b"]},
    ]
    result = generate_mock_historical_data(base_topics, 2025)
    assert result["year"] == 2025
    assert result["historical_topic_count"] == len(base_topics)
    assert len(result["topics"]) == len(base_topics)
    assert len(result["emerged_technologies"]) == 0


def test_generate_mock_historical_data_earlier_year():
    base_topics = [
        {"name": f"技术{i}", "keywords": [f"kw{i}"]} for i in range(20)
    ]
    result = generate_mock_historical_data(base_topics, 2020)
    assert result["year"] == 2020
    assert result["total_topics"] == 20
    assert result["historical_topic_count"] <= 20
    assert result["historical_topic_count"] >= 8
    assert isinstance(result["topics"], list)
    assert isinstance(result["emerged_technologies"], list)
    assert isinstance(result["maturity_levels"], dict)


def test_generate_mock_historical_data_maturity_levels():
    base_topics = [
        {"name": "技术A", "keywords": ["a"]},
        {"name": "技术B", "keywords": ["b"]},
    ]
    result = generate_mock_historical_data(base_topics, 2020)
    for topic in result["topics"]:
        assert "maturity_level" in topic
        assert 0.0 <= topic["maturity_level"] <= 1.0
    for name, maturity in result["maturity_levels"].items():
        assert 0.0 <= maturity <= 1.0


def test_generate_mock_historical_data_empty_topics():
    result = generate_mock_historical_data([], 2020)
    assert result["year"] == 2020
    assert result["topics"] == []
    assert result["emerged_technologies"] == []
    assert result["maturity_levels"] == {}


def test_calculate_metrics_perfect_match():
    forecasted = [
        {"name": "技术A", "forecast_year": 2025, "trend": "up"},
        {"name": "技术B", "forecast_year": 2026, "trend": "up"},
    ]
    actual = [
        {"name": "技术A", "actual_year": 2025, "trend": "up"},
        {"name": "技术B", "actual_year": 2026, "trend": "up"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["accuracy"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["time_deviation"] == 0.0
    assert metrics["direction_accuracy"] == 1.0
    assert metrics["correct_predictions"] == 2


def test_calculate_metrics_all_wrong():
    forecasted = [
        {"name": "技术X", "forecast_year": 2025, "trend": "up"},
        {"name": "技术Y", "forecast_year": 2026, "trend": "up"},
    ]
    actual = [
        {"name": "技术A", "actual_year": 2025, "trend": "up"},
        {"name": "技术B", "actual_year": 2026, "trend": "up"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["accuracy"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["correct_predictions"] == 0


def test_calculate_metrics_partial_match():
    forecasted = [
        {"name": "技术A", "forecast_year": 2025, "trend": "up"},
        {"name": "技术B", "forecast_year": 2026, "trend": "down"},
        {"name": "技术C", "forecast_year": 2027, "trend": "up"},
    ]
    actual = [
        {"name": "技术A", "actual_year": 2025, "trend": "up"},
        {"name": "技术B", "actual_year": 2028, "trend": "up"},
        {"name": "技术D", "actual_year": 2026, "trend": "up"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["correct_predictions"] == 2
    assert abs(metrics["accuracy"] - 2 / 3) < 0.001
    assert abs(metrics["recall"] - 2 / 3) < 0.001
    assert abs(metrics["precision"] - 2 / 3) < 0.001
    assert 0 < metrics["f1_score"] < 1
    assert "技术C" in metrics["false_positives"]
    assert "技术D" in metrics["false_negatives"]


def test_calculate_metrics_time_deviation():
    forecasted = [
        {"name": "技术A", "forecast_year": 2025, "trend": "up"},
        {"name": "技术B", "forecast_year": 2030, "trend": "up"},
    ]
    actual = [
        {"name": "技术A", "actual_year": 2027, "trend": "up"},
        {"name": "技术B", "actual_year": 2025, "trend": "up"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["time_deviation"] == 3.5


def test_calculate_metrics_direction_accuracy():
    forecasted = [
        {"name": "技术A", "forecast_year": 2025, "trend": "up"},
        {"name": "技术B", "forecast_year": 2026, "trend": "down"},
        {"name": "技术C", "forecast_year": 2027, "trend": "up"},
    ]
    actual = [
        {"name": "技术A", "actual_year": 2025, "trend": "up"},
        {"name": "技术B", "actual_year": 2026, "trend": "up"},
        {"name": "技术C", "actual_year": 2027, "trend": "down"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert abs(metrics["direction_accuracy"] - 1 / 3) < 0.001


def test_calculate_metrics_empty_forecast():
    forecasted = []
    actual = [
        {"name": "技术A", "actual_year": 2025, "trend": "up"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["accuracy"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["forecast_count"] == 0
    assert metrics["actual_count"] == 1


def test_calculate_metrics_empty_actual():
    forecasted = [
        {"name": "技术A", "forecast_year": 2025, "trend": "up"},
    ]
    actual = []
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["accuracy"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["forecast_count"] == 1
    assert metrics["actual_count"] == 0


def test_calculate_metrics_both_empty():
    metrics = calculate_metrics([], [], 2030, 2025)
    assert metrics["accuracy"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["forecast_count"] == 0
    assert metrics["actual_count"] == 0
    assert metrics["correct_predictions"] == 0


def test_calculate_metrics_topic_name_field():
    forecasted = [
        {"topic_name": "技术A", "forecast_year": 2025, "trend": "up"},
    ]
    actual = [
        {"topic_name": "技术A", "actual_year": 2025, "trend": "up"},
    ]
    metrics = calculate_metrics(forecasted, actual, 2030, 2025)
    assert metrics["correct_predictions"] == 1
    assert metrics["accuracy"] == 1.0


def test_generate_report_basic():
    results = {
        "historical_year": 2020,
        "forecast_year": 2030,
        "actual_year": 2025,
        "metrics": {
            "accuracy": 0.75,
            "recall": 0.6,
            "precision": 0.75,
            "f1_score": 0.6667,
            "time_deviation": 2.5,
            "direction_accuracy": 0.8,
            "forecast_count": 8,
            "actual_count": 10,
            "correct_predictions": 6,
            "false_positives": ["技术X", "技术Y"],
            "false_negatives": ["技术A", "技术B", "技术C", "技术D"],
            "correct_predictions_list": ["技术1", "技术2", "技术3", "技术4", "技术5", "技术6"],
        },
        "details": [
            {
                "name": "技术1",
                "forecast_year": 2025,
                "actual_year": 2026,
                "time_deviation": 1.0,
                "forecast_trend": "up",
                "actual_trend": "up",
                "direction_correct": True,
            }
        ],
    }
    report = generate_report(results)
    assert "# 回溯验证报告" in report
    assert "历史基准年份: 2020" in report
    assert "预测目标年份: 2030" in report
    assert "实际对照年份: 2025" in report
    assert "准确率 (Accuracy)" in report
    assert "召回率 (Recall)" in report
    assert "F1分数" in report
    assert "时间偏差" in report
    assert "方向准确率" in report
    assert "误报分析" in report
    assert "漏报分析" in report
    assert "正确预测列表" in report
    assert "详细对比" in report
    assert "技术X" in report
    assert "技术A" in report


def test_generate_report_no_errors():
    results = {
        "historical_year": 2020,
        "forecast_year": 2030,
        "actual_year": 2025,
        "metrics": {
            "accuracy": 1.0,
            "recall": 1.0,
            "precision": 1.0,
            "f1_score": 1.0,
            "time_deviation": 0.0,
            "direction_accuracy": 1.0,
            "forecast_count": 3,
            "actual_count": 3,
            "correct_predictions": 3,
            "false_positives": [],
            "false_negatives": [],
            "correct_predictions_list": ["技术A", "技术B", "技术C"],
        },
        "details": [],
    }
    report = generate_report(results)
    assert "# 回溯验证报告" in report
    assert "误报分析" not in report
    assert "漏报分析" not in report


def test_generate_report_empty_results():
    results = {
        "historical_year": 2020,
        "forecast_year": 2030,
        "actual_year": 2025,
        "metrics": {
            "accuracy": 0.0,
            "recall": 0.0,
            "precision": 0.0,
            "f1_score": 0.0,
            "time_deviation": 0.0,
            "direction_accuracy": 0.0,
            "forecast_count": 0,
            "actual_count": 0,
            "correct_predictions": 0,
            "false_positives": [],
            "false_negatives": [],
            "correct_predictions_list": [],
        },
        "details": [],
    }
    report = generate_report(results)
    assert "# 回溯验证报告" in report
    assert "预测技术总数: 0" in report
    assert "正确预测数: 0" in report


def test_backtester_run_backtest_with_mock_data():
    historical_data = {
        "year": 2020,
        "topics": [
            {"name": "技术A", "keywords": ["a"], "maturity_level": 0.3},
            {"name": "技术B", "keywords": ["b"], "maturity_level": 0.4},
        ],
        "emerged_technologies": [],
        "maturity_levels": {"技术A": 0.3, "技术B": 0.4},
    }
    backtester = Backtester(historical_data=historical_data)

    def mock_forecast(topics, target_year):
        return [
            {"name": t["name"], "forecast_year": target_year, "trend": "up"}
            for t in topics
        ]

    results = backtester.run_backtest(
        forecast_func=mock_forecast,
        forecast_year=2025,
        actual_year=2025,
    )

    assert results["historical_year"] == 2020
    assert results["forecast_year"] == 2025
    assert results["actual_year"] == 2025
    assert "metrics" in results
    assert "details" in results
    assert "forecasted" in results
    assert "actual" in results
    assert isinstance(results["metrics"]["accuracy"], float)
    assert isinstance(results["details"], list)
    assert backtester.results is not None


def test_backtester_generate_report_before_run():
    backtester = Backtester()
    report = backtester.generate_report()
    assert "尚未运行回溯验证" in report


def test_backtester_generate_report_after_run():
    historical_data = {
        "year": 2020,
        "topics": [
            {"name": "技术A", "keywords": ["a"], "maturity_level": 0.3},
        ],
        "emerged_technologies": [],
        "maturity_levels": {"技术A": 0.3},
    }
    backtester = Backtester(historical_data=historical_data)

    def mock_forecast(topics, target_year):
        return [{"name": t["name"], "forecast_year": target_year, "trend": "up"} for t in topics]

    backtester.run_backtest(
        forecast_func=mock_forecast,
        forecast_year=2025,
        actual_year=2025,
    )

    report = backtester.generate_report()
    assert "# 回溯验证报告" in report
    assert "历史基准年份: 2020" in report


def test_calculate_metrics_f1_score():
    forecasted = [{"name": f"技术{i}", "forecast_year": 2025, "trend": "up"} for i in range(10)]
    actual = [{"name": f"技术{i}", "actual_year": 2025, "trend": "up"} for i in range(5, 15)]

    metrics = calculate_metrics(forecasted, actual, 2030, 2025)

    precision = 5 / 10
    recall = 5 / 10
    expected_f1 = 2 * precision * recall / (precision + recall)

    assert abs(metrics["precision"] - precision) < 0.001
    assert abs(metrics["recall"] - recall) < 0.001
    assert abs(metrics["f1_score"] - expected_f1) < 0.001


def test_generate_mock_historical_data_deterministic_with_seed():
    import random
    base_topics = [
        {"name": f"技术{i}", "keywords": [f"kw{i}"]} for i in range(10)
    ]

    random.seed(42)
    result1 = generate_mock_historical_data(base_topics, 2020)

    random.seed(42)
    result2 = generate_mock_historical_data(base_topics, 2020)

    assert result1["historical_topic_count"] == result2["historical_topic_count"]
    assert len(result1["topics"]) == len(result2["topics"])


def test_backtester_details_structure():
    historical_data = {
        "year": 2020,
        "topics": [
            {"name": "技术A", "keywords": ["a"]},
            {"name": "技术B", "keywords": ["b"]},
        ],
        "emerged_technologies": [],
        "maturity_levels": {},
    }
    backtester = Backtester(historical_data=historical_data)

    def mock_forecast(topics, target_year):
        return [{"name": "技术A", "forecast_year": target_year, "trend": "up"}]

    results = backtester.run_backtest(
        forecast_func=mock_forecast,
        forecast_year=2025,
        actual_year=2025,
    )

    details = results["details"]
    assert len(details) >= 1
    for d in details:
        assert "name" in d
        assert "forecast_year" in d
        assert "actual_year" in d
        assert "time_deviation" in d
        assert "forecast_trend" in d
        assert "actual_trend" in d
        assert "direction_correct" in d
        assert "in_forecast" in d
        assert "in_actual" in d


def run_all_tests():
    test_funcs = [
        test_backtester_init_default,
        test_backtester_init_with_data,
        test_generate_mock_historical_data_same_year,
        test_generate_mock_historical_data_earlier_year,
        test_generate_mock_historical_data_maturity_levels,
        test_generate_mock_historical_data_empty_topics,
        test_calculate_metrics_perfect_match,
        test_calculate_metrics_all_wrong,
        test_calculate_metrics_partial_match,
        test_calculate_metrics_time_deviation,
        test_calculate_metrics_direction_accuracy,
        test_calculate_metrics_empty_forecast,
        test_calculate_metrics_empty_actual,
        test_calculate_metrics_both_empty,
        test_calculate_metrics_topic_name_field,
        test_generate_report_basic,
        test_generate_report_no_errors,
        test_generate_report_empty_results,
        test_backtester_run_backtest_with_mock_data,
        test_backtester_generate_report_before_run,
        test_backtester_generate_report_after_run,
        test_calculate_metrics_f1_score,
        test_generate_mock_historical_data_deterministic_with_seed,
        test_backtester_details_structure,
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
