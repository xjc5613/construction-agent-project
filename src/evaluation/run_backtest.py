# -*- coding:utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse
import json

from src.evaluation.backtesting import Backtester, generate_mock_historical_data
from src.utils.file_io import read_json, write_text
from config.settings import BACKTEST_HISTORICAL_YEAR, DATA_RAW, OUTPUTS_REPORT


def mock_forecast_func(historical_topics, forecast_year):
    forecasted = []
    for topic in historical_topics:
        name = topic.get("name", "")
        forecasted.append({
            "name": name,
            "forecast_year": forecast_year,
            "trend": "up",
            "confidence": 0.7,
        })
    return forecasted


def run_backtest_from_cli(args):
    historical_year = args.historical_year or BACKTEST_HISTORICAL_YEAR
    forecast_year = args.forecast_year
    actual_year = args.actual_year

    topics_path = DATA_RAW / "topics.json"
    base_topics = read_json(topics_path) or []

    historical_data = generate_mock_historical_data(base_topics, historical_year)

    backtester = Backtester(historical_data=historical_data)

    results = backtester.run_backtest(
        forecast_func=mock_forecast_func,
        forecast_year=forecast_year,
        actual_year=actual_year,
    )

    report = backtester.generate_report()

    if args.output:
        output_path = args.output
    else:
        output_path = OUTPUTS_REPORT / f"backtest_report_{historical_year}_{forecast_year}.md"

    write_text(report, output_path)
    print(f"\n回溯验证报告已保存至: {output_path}")
    print("\n" + "=" * 60)
    print(report)

    if args.json_output:
        json_path = args.json_output
    else:
        json_path = OUTPUTS_REPORT / f"backtest_results_{historical_year}_{forecast_year}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n详细结果 JSON 已保存至: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="智能建造2040技术预测 - 回溯验证工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    backtest_parser = subparsers.add_parser("backtest", help="运行回溯验证")
    backtest_parser.add_argument(
        "--historical-year",
        type=int,
        default=None,
        help=f"历史基准年份 (默认: {BACKTEST_HISTORICAL_YEAR})",
    )
    backtest_parser.add_argument(
        "--forecast-year",
        type=int,
        default=2030,
        help="预测目标年份 (默认: 2030)",
    )
    backtest_parser.add_argument(
        "--actual-year",
        type=int,
        default=2025,
        help="实际对照年份 (默认: 2025)",
    )
    backtest_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Markdown 报告输出路径",
    )
    backtest_parser.add_argument(
        "--json-output",
        type=str,
        default=None,
        help="JSON 结果输出路径",
    )

    args = parser.parse_args()

    if args.command == "backtest":
        run_backtest_from_cli(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
