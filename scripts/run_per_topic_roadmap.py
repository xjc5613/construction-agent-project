# -*- coding:utf-8 -*-
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import setup_logger
from src.llm_orchestrator import run_all_topics_roadmap
from src.report.per_topic_roadmap_report import save_per_topic_reports
from src.utils.file_io import read_json
from config.settings import OUTPUTS_PARSED

logger = setup_logger("per_topic_roadmap")


def load_round1_results():
    round1_files = sorted(OUTPUTS_PARSED.glob("round1_*.json"))
    results = []
    for f in round1_files:
        data = read_json(f)
        if data:
            results.append(data)
    return results


def main():
    parser = argparse.ArgumentParser(description="生成分主题技术路线图")
    parser.add_argument("--force-rerun", action="store_true", help="强制重新生成，忽略缓存")
    args = parser.parse_args()

    force_rerun = args.force_rerun

    logger.info("=" * 60)
    logger.info("===== 分主题技术路线图生成 =====")
    logger.info("=" * 60)

    logger.info("步骤1: 加载第一轮预测结果")
    round1_results = load_round1_results()

    if not round1_results:
        logger.error("未找到第一轮预测结果，请先运行完整预测流程")
        logger.info(f"查找路径: {OUTPUTS_PARSED}")
        sys.exit(1)

    logger.info(f"已加载 {len(round1_results)} 个主题的第一轮结果")

    logger.info("步骤2: 生成分主题技术路线图")
    roadmaps = run_all_topics_roadmap(round1_results, force_rerun=force_rerun)

    if not roadmaps:
        logger.error("分主题路线图生成失败")
        sys.exit(1)

    logger.info(f"成功生成 {len(roadmaps)} 个主题的路线图")

    logger.info("步骤3: 保存报告文件")
    all_report_path, single_paths = save_per_topic_reports(roadmaps)

    logger.info("=" * 60)
    logger.info("===== 生成完成 =====")
    logger.info("=" * 60)
    logger.info(f"整合报告: {all_report_path}")
    logger.info(f"单主题报告 ({len(single_paths)} 个):")
    for p in single_paths:
        logger.info(f"  - {p}")


if __name__ == "__main__":
    main()
