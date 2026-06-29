# -*- coding:utf-8 -*-
import json
from typing import List, Dict, Any, Optional, Callable
from src.utils.logger import get_logger
from .self_consistency import calculate_confidence

logger = get_logger(__name__)

AGENT_SYSTEM_PROMPTS = {
    "tech_expert": """你是一位智能建造领域的技术专家，拥有20年以上建筑工程技术研发经验。你的评审重点是：
1. 技术可行性：预测的技术路线在工程上是否可实现，是否符合技术发展规律
2. 技术成熟度：各阶段（2030-2035、2040）的技术成熟度判断是否合理，TRL等级是否准确
3. 技术路线合理性：从当前技术到预测目标的演进路径是否清晰、可行
4. 技术细节准确性：涉及的具体技术概念、参数、指标是否准确

请基于你对智能建造领域（包括建筑机器人、数字孪生、BIM、装配式建筑、增材制造等）的深入理解，对预测结果进行严格评审。输出格式包含：优点、主要问题、改进建议。""",

    "industry_analyst": """你是一位智能建造产业分析师，专注于建筑行业技术产业化和市场应用研究。你的评审重点是：
1. 产业化路径：技术从实验室到规模化应用的路径是否清晰，关键节点是否合理
2. 市场需求：预测的技术是否有真实的市场驱动力，需求规模判断是否合理
3. 成本效益：技术应用的成本下降曲线、投资回报周期是否合理
4. 应用场景：预测的应用场景是否真实存在，是否符合建筑行业实际痛点

请基于建筑行业的产业规律、市场规模、供应链特点、政策环境等因素进行评审。输出格式包含：优点、主要问题、改进建议。""",

    "risk_assessor": """你是一位智能建造技术风险评估师，擅长识别技术发展中的不确定性和潜在风险。你的评审重点是：
1. 技术风险：关键技术难点是否被充分识别，失败概率评估是否合理
2. 不确定性：预测中哪些部分不确定性较高，是否被明确标注
3. 潜在问题：可能导致预测偏差的隐藏因素，如政策变化、供应链瓶颈、人才短缺等
4. 发展瓶颈：制约技术发展的核心瓶颈是否被准确识别，突破难度评估是否合理

请从风险和不确定性的角度，对预测的可靠性进行审慎评估。输出格式包含：优点、主要问题、改进建议。""",

    "methodology_expert": """你是一位技术预测方法论专家，精通德尔菲法、情景分析、技术路线图等预测方法。你的评审重点是：
1. 预测方法论：预测的逻辑和方法是否科学，是否有明确的推理链条
2. 依据充分性：预测结论是否有足够的证据支撑，引用的数据和案例是否可靠
3. 逻辑严谨性：推理过程是否存在逻辑漏洞，假设条件是否明确且合理
4. 时间锚定准确性：各时间节点的预测是否符合技术发展的客观规律

请从方法论的角度，评估预测结果的科学性和严谨性。输出格式包含：优点、主要问题、改进建议。"""
}

AGENT_REVIEW_QUESTIONS = {
    "tech_expert": [
        "预测的技术路线在工程实现上是否可行？有无技术上的硬伤？",
        "各阶段技术成熟度（TRL等级）判断是否合理？",
        "从当前技术水平到2030-2035瓶颈、2040突破的演进路径是否清晰？",
        "涉及的具体技术概念和指标是否准确，有无明显错误？"
    ],
    "industry_analyst": [
        "预测的技术是否有真实的市场需求支撑？",
        "产业化路径（从原型到规模化应用）是否合理？",
        "成本效益分析是否符合行业实际？",
        "应用场景是否真实反映建筑行业痛点？"
    ],
    "risk_assessor": [
        "预测中识别的技术风险是否全面？有无遗漏的重大风险？",
        "不确定性高的部分是否被明确标注和讨论？",
        "潜在的外部因素（政策、供应链、人才等）是否被考虑？",
        "技术瓶颈的突破难度评估是否合理？"
    ],
    "methodology_expert": [
        "预测的推理逻辑是否清晰、严谨？",
        "结论是否有充分的证据和数据支撑？",
        "假设条件是否明确且合理？",
        "时间节点的锚定是否符合技术发展规律？"
    ]
}

AGENT_NAMES_CN = {
    "tech_expert": "技术专家",
    "industry_analyst": "产业分析师",
    "risk_assessor": "风险评估师",
    "methodology_expert": "方法论专家"
}


def build_agent_review_messages(initial_result: Dict[str, Any], agent_role: str, context_info: str = "") -> List[Dict[str, str]]:
    system_prompt = AGENT_SYSTEM_PROMPTS.get(agent_role, "")
    questions = AGENT_REVIEW_QUESTIONS.get(agent_role, [])
    agent_name = AGENT_NAMES_CN.get(agent_role, agent_role)

    questions_str = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    result_str = json.dumps(initial_result, ensure_ascii=False, indent=2)

    user_prompt = f"""请你以{agent_name}的身份，对以下智能建造技术预测结果进行评审。

【背景信息】
{context_info if context_info else "（无额外背景信息）"}

【待评审预测结果】
{result_str}

【评审要点】
{questions_str}

请按照以下格式输出你的评审意见：
【优点】
（列出预测结果中做得好的地方）

【主要问题】
（列出你发现的主要问题和质疑点，逐条说明）

【改进建议】
（针对上述问题，提出具体的改进建议）

请务必基于智能建造领域的专业知识进行评审，意见要具体、有建设性，避免泛泛而谈。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def build_revision_messages(initial_result: Dict[str, Any], reviews: Dict[str, str], context_info: str = "") -> List[Dict[str, str]]:
    reviews_str = ""
    for agent_key, review_text in reviews.items():
        agent_name = AGENT_NAMES_CN.get(agent_key, agent_key)
        reviews_str += f"\n=== {agent_name}评审意见 ===\n{review_text}\n"

    result_str = json.dumps(initial_result, ensure_ascii=False, indent=2)

    system_prompt = """你是一位智能建造领域的未来学家，擅长技术预测。现在请你根据多位专家的评审意见，对之前的预测结果进行修正和优化。

请认真考虑每一位专家的意见，吸收合理的建议，修正存在的问题。如果对某些意见有不同看法，也可以在结果中说明理由。

修正后的预测结果必须保持原有的JSON格式结构，确保可以被正确解析。"""

    user_prompt = f"""【原始预测结果】
{result_str}

【专家评审意见汇总】
{reviews_str}

【背景信息】
{context_info if context_info else "（无额外背景信息）"}

请根据以上评审意见，对预测结果进行修正和优化。输出修正后的完整JSON格式预测结果，并在最后简要说明主要修改点。

注意：
1. 保持原有的JSON结构和字段不变
2. 只修改内容，不改变格式
3. 确保输出是有效的JSON"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def build_debate_summary_messages(all_reviews: List[Dict[str, Any]], final_result: Dict[str, Any]) -> List[Dict[str, str]]:
    reviews_text = ""
    for round_idx, round_data in enumerate(all_reviews):
        reviews_text += f"\n=== 第{round_idx + 1}轮评审 ===\n"
        for agent_key, review_text in round_data.get("reviews", {}).items():
            agent_name = AGENT_NAMES_CN.get(agent_key, agent_key)
            reviews_text += f"\n--- {agent_name} ---\n{review_text}\n"

    final_str = json.dumps(final_result, ensure_ascii=False, indent=2)

    system_prompt = """你是一位技术预测项目的总结专家，请根据多轮辩论评审的记录，生成一份辩论摘要。"""

    user_prompt = f"""【辩论评审记录】
{reviews_text}

【最终预测结果】
{final_str}

请生成一份辩论摘要，包含以下内容：
1. 关键争议点：各专家有不同看法的问题
2. 达成共识的内容：各方都认可的部分
3. 仍存疑的问题：未能充分解决的疑问

请用简洁明了的语言总结，分点列出。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def _parse_review_text(text: str) -> Dict[str, List[str]]:
    result = {
        "strengths": [],
        "issues": [],
        "suggestions": []
    }
    if not text:
        return result

    current_section = None
    for line in text.split("\n"):
        stripped = line.strip()
        if "优点" in stripped and ("【" in stripped or "[" in stripped):
            current_section = "strengths"
            continue
        elif "主要问题" in stripped and ("【" in stripped or "[" in stripped):
            current_section = "issues"
            continue
        elif "改进建议" in stripped and ("【" in stripped or "[" in stripped):
            current_section = "suggestions"
            continue
        elif stripped and current_section:
            cleaned = stripped.lstrip("-•*0123456789.、)").strip()
            if cleaned:
                result[current_section].append(cleaned)

    return result


class DebateEngine:
    def __init__(self, llm_client, agents: List[str] = None, num_rounds: int = 2,
                 confidence_threshold: float = 60.0):
        self.llm_client = llm_client
        self.num_rounds = max(1, num_rounds)
        self.confidence_threshold = confidence_threshold

        all_agents = list(AGENT_SYSTEM_PROMPTS.keys())
        if agents is None:
            self.agents = all_agents
        else:
            self.agents = [a for a in agents if a in all_agents]
            if not self.agents:
                logger.warning("指定的Agent列表无效，使用全部Agent")
                self.agents = all_agents

        logger.info(f"辩论引擎初始化 - Agents: {self.agents}, 轮数: {self.num_rounds}")

    def _run_single_review(self, initial_result: Dict[str, Any], agent_role: str,
                           context_info: str = "") -> Optional[str]:
        try:
            msgs = build_agent_review_messages(initial_result, agent_role, context_info)
            resp = self.llm_client.chat_completion(msgs)
            return resp
        except Exception as e:
            logger.warning(f"Agent {agent_role} 评审失败: {e}")
            return None

    def _run_all_reviews(self, current_result: Dict[str, Any],
                         context_info: str = "") -> Dict[str, str]:
        reviews = {}
        for agent in self.agents:
            agent_name = AGENT_NAMES_CN.get(agent, agent)
            logger.info(f"辩论评审 - {agent_name} 正在评审...")
            review = self._run_single_review(current_result, agent, context_info)
            if review:
                reviews[agent] = review
                logger.info(f"辩论评审 - {agent_name} 评审完成")
            else:
                logger.warning(f"辩论评审 - {agent_name} 评审失败，已跳过")
        return reviews

    def _run_revision(self, current_result: Dict[str, Any], reviews: Dict[str, str],
                      context_info: str = "") -> Optional[str]:
        if not reviews:
            logger.warning("没有有效评审意见，跳过修正")
            return None
        try:
            msgs = build_revision_messages(current_result, reviews, context_info)
            resp = self.llm_client.chat_completion(msgs)
            return resp
        except Exception as e:
            logger.warning(f"修正预测失败: {e}")
            return None

    def _generate_summary(self, all_reviews: List[Dict[str, Any]],
                          final_result: Dict[str, Any]) -> Optional[str]:
        try:
            msgs = build_debate_summary_messages(all_reviews, final_result)
            resp = self.llm_client.chat_completion(msgs)
            return resp
        except Exception as e:
            logger.warning(f"生成辩论摘要失败: {e}")
            return None

    def run(self, initial_messages: List[Dict[str, str]],
            initial_result: Dict[str, Any],
            parser_func: Callable[..., Optional[Any]],
            parser_args: Optional[tuple] = None,
            parser_kwargs: Optional[Dict[str, Any]] = None,
            context_info: str = "") -> Dict[str, Any]:
        if parser_args is None:
            parser_args = ()
        if parser_kwargs is None:
            parser_kwargs = {}

        if not initial_result:
            logger.error("初始预测结果为空，无法进行辩论")
            return {
                "success": False,
                "error": "初始预测结果为空",
                "final_result": None,
                "debate_rounds": 0,
            }

        current_result = initial_result
        all_reviews = []
        all_parsed_results = [initial_result]
        successful_agents = set()

        for round_idx in range(self.num_rounds):
            logger.info(f"辩论 - 第{round_idx + 1}/{self.num_rounds}轮")

            reviews = self._run_all_reviews(current_result, context_info)
            if not reviews:
                logger.warning("本轮无有效评审意见，辩论提前结束")
                break

            for agent_key in reviews.keys():
                successful_agents.add(agent_key)

            all_reviews.append({
                "round": round_idx + 1,
                "reviews": reviews
            })

            if round_idx < self.num_rounds - 1:
                revision_text = self._run_revision(current_result, reviews, context_info)
                if not revision_text:
                    logger.warning("修正失败，保持当前结果")
                    break

                try:
                    parsed = parser_func(revision_text, *parser_args, **parser_kwargs)
                    if parsed and isinstance(parsed, dict):
                        current_result = parsed
                        all_parsed_results.append(parsed)
                        logger.info(f"第{round_idx + 1}轮修正完成")
                    else:
                        logger.warning("修正结果解析失败，保持当前结果")
                        break
                except Exception as e:
                    logger.warning(f"修正结果解析异常: {e}")
                    break

        logger.info(f"辩论完成 - 共{len(all_reviews)}轮有效评审, {len(all_parsed_results)}个版本结果")

        confidence = 50.0
        if len(all_parsed_results) > 1:
            confidence = calculate_confidence(all_parsed_results)

        summary = self._generate_summary(all_reviews, current_result)

        result = dict(current_result) if isinstance(current_result, dict) else {}
        result["debate_info"] = {
            "success": True,
            "num_rounds": len(all_reviews),
            "total_rounds_configured": self.num_rounds,
            "agents_used": list(successful_agents),
            "confidence": round(confidence, 2),
            "confidence_threshold": self.confidence_threshold,
            "debate_summary": summary or "",
            "review_details": all_reviews,
            "num_versions": len(all_parsed_results),
        }

        return result
