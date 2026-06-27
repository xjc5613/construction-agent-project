# -*- coding:utf-8-*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import setup_logger
from src.data_preparation.build_round1_inputs import build_round1_inputs
from src.llm_orchestrator import run_round1, run_round2, run_round3
from src.report_generator import generate_final_report

logger = setup_logger("main")

def main():
    logger.info("===== 智能建造2040技术预测系统启动 =====")
    logger.info("步骤1: 构造第一轮输入数据")
    topic_inputs = build_round1_inputs()
    if not topic_inputs:
        logger.error("无有效主题输入，退出")
        return

    logger.info("步骤2: 执行第一轮预测（主题演化）")
    round1_results = run_round1(topic_inputs, force_rerun=False)
    if not round1_results:
        logger.error("第一轮无结果，退出")
        return

    logger.info("步骤3: 执行第二轮预测（新范式）")
    round2_result = run_round2(round1_results, force_rerun=False)

    logger.info("步骤4: 执行第三轮预测（路线图）")
    round3_result = run_round3(round1_results, round2_result, force_rerun=False)

    logger.info("步骤5: 生成最终报告")
    generate_final_report(round1_results, round2_result, round3_result)

    logger.info("===== 所有任务完成 =====")

if __name__ == "__main__":
    main()