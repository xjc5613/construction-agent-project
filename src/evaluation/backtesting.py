# -*- coding:utf-8 -*-
import copy
import random
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

from src.utils.logger import get_logger
from src.utils.file_io import read_json
from config.settings import BACKTEST_HISTORICAL_YEAR, DATA_RAW

logger = get_logger(__name__)


def generate_mock_historical_data(base_topics: List[Dict], historical_year: int) -> Dict[str, Any]:
    current_year = 2025
    year_diff = current_year - historical_year
    if year_diff <= 0:
        maturity_levels = {}
        for i, topic in enumerate(base_topics):
            topic_name = topic.get("name", f"topic_{i}")
            current_maturity = 0.5 + 0.1 * (i % 5)
            maturity_levels[topic_name] = round(current_maturity, 2)
        return {
            "year": historical_year,
            "topics": copy.deepcopy(base_topics),
            "emerged_technologies": [],
            "maturity_levels": maturity_levels,
            "total_topics": len(base_topics),
            "historical_topic_count": len(base_topics),
        }

    removal_ratio = min(0.1 + 0.05 * year_diff, 0.6)
    maturity_reduction = min(0.1 + 0.03 * year_diff, 0.5)

    historical_topics = []
    emerged_technologies = []
    maturity_levels = {}

    for i, topic in enumerate(base_topics):
        topic_name = topic.get("name", f"topic_{i}")
        current_maturity = 0.5 + 0.1 * (i % 5)
        historical_maturity = max(0.1, current_maturity - maturity_reduction)

        if random.random() < removal_ratio and i > len(base_topics) * 0.5:
            emerged_technologies.append({
                "name": topic_name,
                "emerged_year": historical_year + random.randint(1, year_diff),
                "maturity_at_emerge": historical_maturity + 0.1,
            })
            continue

        historical_topic = copy.deepcopy(topic)
        historical_topic["maturity_level"] = round(historical_maturity, 2)
        historical_topics.append(historical_topic)
        maturity_levels[topic_name] = round(historical_maturity, 2)

    result = {
        "year": historical_year,
            "topics": historical_topics,
            "emerged_technologies": emerged_technologies,
            "maturity_levels": maturity_levels,
            "total_topics": len(base_topics),
            "historical_topic_count": len(historical_topics),
        }

    logger.info(
        f"生成 {historical_year}年模拟数据: "
        f"{len(historical_topics)} 个已有主题, "
        f"{len(emerged_technologies)} 个后续涌现技术"
    )
    return result


def _generate_actual_development(
    base_topics: List[Dict], historical_year: int, actual_year: int
) -> Dict[str, Any]:
    current_year = 2025
    actual_year = min(actual_year, current_year)
    year_diff = actual_year - historical_year

    actual_topics = copy.deepcopy(base_topics)
    actual_maturity = {}
    emerged_by_year = {year: [] for year in range(historical_year + 1, actual_year + 1)}

    for i, topic in enumerate(actual_topics):
        topic_name = topic.get("name", f"topic_{i}")
        base_maturity = 0.5 + 0.1 * (i % 5)
        growth = min(0.02 * year_diff, 0.4)
        actual_maturity[topic_name] = round(min(base_maturity + growth, 0.95), 2)
        topic["maturity_level"] = round(min(base_maturity + growth, 0.95), 2)

        if i > len(base_topics) * 0.6:
            emerge_year = historical_year + random.randint(1, max(1, year_diff))
            if emerge_year <= actual_year:
                emerged_by_year[emerge_year].append(topic_name)

    result = {
        "year": actual_year,
        "topics": actual_topics,
        "maturity_levels": actual_maturity,
        "emerged_by_year": emerged_by_year,
    }
    return result


def calculate_metrics(
    forecasted: List[Dict],
    actual: List[Dict],
    forecast_year: int,
    actual_year: int,
) -> Dict[str, Any]:
    if not forecasted or not actual:
        return {
            "accuracy": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "precision": 0.0,
            "time_deviation": 0.0,
            "direction_accuracy": 0.0,
            "forecast_count": len(forecasted) if forecasted else 0,
            "actual_count": len(actual) if actual else 0,
            "correct_predictions": 0,
        }

    forecast_names = {f.get("name", f.get("topic_name", "")) for f in forecasted}
    actual_names = {a.get("name", a.get("topic_name", "")) for a in actual}

    correct = forecast_names & actual_names
    false_positives = forecast_names - actual_names
    false_negatives = actual_names - forecast_names

    precision = len(correct) / len(forecast_names) if forecast_names else 0.0
    recall = len(correct) / len(actual_names) if actual_names else 0.0
    accuracy = len(correct) / len(forecast_names) if forecast_names else 0.0

    if precision + recall > 0:
        f1_score = 2 * precision * recall / (precision + recall)
    else:
        f1_score = 0.0

    time_deviations = []
    direction_correct = 0
    direction_total = 0

    actual_map = {a.get("name", a.get("topic_name", "")): a for a in actual}
    forecast_map = {f.get("name", f.get("topic_name", "")): f for f in forecasted}

    for name in correct:
        f_item = forecast_map.get(name, {})
        a_item = actual_map.get(name, {})

        f_year = f_item.get("forecast_year", f_item.get("year", forecast_year))
        a_year = a_item.get("actual_year", a_item.get("year", actual_year))

        if isinstance(f_year, (int, float)) and isinstance(a_year, (int, float)):
            time_deviations.append(abs(f_year - a_year))

        f_trend = f_item.get("trend", f_item.get("direction", "up"))
        a_trend = a_item.get("trend", a_item.get("direction", "up"))
        direction_total += 1
        if f_trend == a_trend:
            direction_correct += 1

    avg_time_deviation = sum(time_deviations) / len(time_deviations) if time_deviations else 0.0
    direction_accuracy = direction_correct / direction_total if direction_total > 0 else 0.0

    metrics = {
        "accuracy": round(accuracy, 4),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1_score": round(f1_score, 4),
        "time_deviation": round(avg_time_deviation, 2),
        "direction_accuracy": round(direction_accuracy, 4),
        "forecast_count": len(forecast_names),
        "actual_count": len(actual_names),
        "correct_predictions": len(correct),
        "false_positives": list(false_positives),
        "false_negatives": list(false_negatives),
        "correct_predictions_list": list(correct),
    }
    return metrics


def generate_report(results: Dict[str, Any]) -> str:
    metrics = results.get("metrics", {})
    forecast_year = results.get("forecast_year", "N/A")
    actual_year = results.get("actual_year", "N/A")
    historical_year = results.get("historical_year", "N/A")

    lines = []
    lines.append("# 回溯验证报告")
    lines.append("")
    lines.append("## 基本信息")
    lines.append("")
    lines.append(f"- 历史基准年份: {historical_year}")
    lines.append(f"- 预测目标年份: {forecast_year}")
    lines.append(f"- 实际对照年份: {actual_year}")
    lines.append("")
    lines.append("## 评估指标")
    lines.append("")
    lines.append("| 指标 | 数值 | 说明 |")
    lines.append("|------|------|------|")
    lines.append(f"| 准确率 (Accuracy) | {metrics.get('accuracy', 0):.2%} | 预测正确的技术占预测总数的比例 |")
    lines.append(f"| 召回率 (Recall) | {metrics.get('recall', 0):.2%} | 实际发生的技术中被预测到的比例 |")
    lines.append(f"| 精确率 (Precision) | {metrics.get('precision', 0):.2%} | 预测为正的样本中实际为正的比例 |")
    lines.append(f"| F1分数 | {metrics.get('f1_score', 0):.4f} | 准确率和召回率的调和平均 |")
    lines.append(f"| 时间偏差 (年) | {metrics.get('time_deviation', 0):.2f} | 预测时间与实际时间的平均偏差 |")
    lines.append(f"| 方向准确率 | {metrics.get('direction_accuracy', 0):.2%} | 趋势预测方向是否正确 |")
    lines.append("")
    lines.append("## 统计概览")
    lines.append("")
    lines.append(f"- 预测技术总数: {metrics.get('forecast_count', 0)}")
    lines.append(f"- 实际技术总数: {metrics.get('actual_count', 0)}")
    lines.append(f"- 正确预测数: {metrics.get('correct_predictions', 0)}")
    lines.append(f"- 误报数 (False Positives): {len(metrics.get('false_positives', []))}")
    lines.append(f"- 漏报数 (False Negatives): {len(metrics.get('false_negatives', []))}")
    lines.append("")

    if metrics.get("false_positives"):
        lines.append("## 误报分析 (预测了但未发生)")
        lines.append("")
        for idx, name in enumerate(metrics["false_positives"], 1):
            lines.append(f"{idx}. {name}")
        lines.append("")

    if metrics.get("false_negatives"):
        lines.append("## 漏报分析 (发生了但未预测)")
        lines.append("")
        for idx, name in enumerate(metrics["false_negatives"], 1):
            lines.append(f"{idx}. {name}")
        lines.append("")

    if metrics.get("correct_predictions_list"):
        lines.append("## 正确预测列表")
        lines.append("")
        for idx, name in enumerate(metrics["correct_predictions_list"], 1):
            lines.append(f"{idx}. {name}")
        lines.append("")

    details = results.get("details", [])
    if details:
        lines.append("## 详细对比")
        lines.append("")
        lines.append("| 技术名称 | 预测年份 | 实际年份 | 时间偏差 | 预测趋势 | 实际趋势 | 方向正确 |")
        lines.append("|----------|----------|----------|----------|----------|----------|----------|")
        for d in details:
            name = d.get("name", "N/A")
            f_year = d.get("forecast_year", "N/A")
            a_year = d.get("actual_year", "N/A")
            t_dev = d.get("time_deviation", "N/A")
            f_trend = d.get("forecast_trend", "N/A")
            a_trend = d.get("actual_trend", "N/A")
            correct = "✓" if d.get("direction_correct", False) else "✗"
            lines.append(f"| {name} | {f_year} | {a_year} | {t_dev} | {f_trend} | {a_trend} | {correct} |")
        lines.append("")

    lines.append("---")
    lines.append("*报告由回溯验证模块自动生成*")

    return "\n".join(lines)


class Backtester:
    def __init__(self, historical_data: Optional[Dict] = None):
        self.historical_data = historical_data
        self.results = None

    def run_backtest(
        self,
        forecast_func: Callable[[List[Dict], int], List[Dict]],
        forecast_year: int,
        actual_year: int,
    ) -> Dict[str, Any]:
        if self.historical_data is None:
            topics_path = DATA_RAW / "topics.json"
            base_topics = read_json(topics_path) or []
            self.historical_data = generate_mock_historical_data(
                base_topics, BACKTEST_HISTORICAL_YEAR
            )

        historical_topics = self.historical_data.get("topics", [])
        historical_year = self.historical_data.get("year", BACKTEST_HISTORICAL_YEAR)

        logger.info(f"开始回溯验证: 基准年={historical_year}, 预测年={forecast_year}, 实际年={actual_year}")

        forecasted = forecast_func(historical_topics, forecast_year)
        logger.info(f"预测完成: 预测了 {len(forecasted)} 项技术")

        actual_data = self._get_actual_data(actual_year)
        actual_topics = actual_data.get("topics", [])
        logger.info(f"实际数据: {len(actual_topics)} 项技术")

        metrics = calculate_metrics(forecasted, actual_topics, forecast_year, actual_year)

        details = self._build_details(forecasted, actual_topics, forecast_year, actual_year)

        self.results = {
            "historical_year": historical_year,
            "forecast_year": forecast_year,
            "actual_year": actual_year,
            "metrics": metrics,
            "details": details,
            "forecasted": forecasted,
            "actual": actual_topics,
        }

        logger.info(
            f"回溯验证完成: 准确率={metrics['accuracy']:.2%}, "
            f"召回率={metrics['recall']:.2%}, F1={metrics['f1_score']:.4f}"
        )
        return self.results

    def _get_actual_data(self, actual_year: int) -> Dict[str, Any]:
        topics_path = DATA_RAW / "topics.json"
        base_topics = read_json(topics_path) or []
        historical_year = self.historical_data.get("year", BACKTEST_HISTORICAL_YEAR)
        return _generate_actual_development(base_topics, historical_year, actual_year)

    def _build_details(
        self,
        forecasted: List[Dict],
        actual: List[Dict],
        forecast_year: int,
        actual_year: int,
    ) -> List[Dict]:
        details = []
        forecast_map = {f.get("name", f.get("topic_name", "")): f for f in forecasted}
        actual_map = {a.get("name", a.get("topic_name", "")): a for a in actual}

        all_names = set(forecast_map.keys()) | set(actual_map.keys())

        for name in all_names:
            f_item = forecast_map.get(name, {})
            a_item = actual_map.get(name, {})

            f_year = f_item.get("forecast_year", f_item.get("year", forecast_year))
            a_year = a_item.get("actual_year", a_item.get("year", actual_year))

            time_dev = ""
            if isinstance(f_year, (int, float)) and isinstance(a_year, (int, float)):
                time_dev = round(abs(f_year - a_year), 2)

            f_trend = f_item.get("trend", f_item.get("direction", "unknown"))
            a_trend = a_item.get("trend", a_item.get("direction", "unknown"))
            direction_correct = f_trend == a_trend if name in forecast_map and name in actual_map else False

            details.append({
                "name": name,
                "forecast_year": f_year,
                "actual_year": a_year,
                "time_deviation": time_dev,
                "forecast_trend": f_trend,
                "actual_trend": a_trend,
                "direction_correct": direction_correct,
                "in_forecast": name in forecast_map,
                "in_actual": name in actual_map,
            })

        return sorted(details, key=lambda x: x["name"])

    def generate_report(self) -> str:
        if self.results is None:
            return "尚未运行回溯验证，请先调用 run_backtest()"
        return generate_report(self.results)
