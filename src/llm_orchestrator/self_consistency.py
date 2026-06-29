# -*- coding:utf-8-*-
import difflib
from typing import List, Dict, Any, Optional, Callable
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _text_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _list_similarity(a: List, b: List) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    set_a = set(str(x) for x in a)
    set_b = set(str(x) for x in b)

    intersection = set_a & set_b
    union = set_a | set_b
    jaccard = len(intersection) / len(union) if union else 0.0

    len_a, len_b = len(a), len(b)
    min_len = min(len_a, len_b)
    if min_len == 0:
        order_sim = 0.0
    else:
        matches = 0
        for i in range(min_len):
            if _text_similarity(str(a[i]), str(b[i])) > 0.6:
                matches += 1
        order_sim = matches / max(len_a, len_b)

    return 0.7 * jaccard + 0.3 * order_sim


def _value_similarity(a: Any, b: Any) -> float:
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    if isinstance(a, list) and isinstance(b, list):
        return _list_similarity(a, b)
    if isinstance(a, str) and isinstance(b, str):
        return _text_similarity(a, b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return 1.0
        max_val = max(abs(a), abs(b))
        if max_val == 0:
            return 1.0
        return 1.0 - abs(a - b) / max_val
    return _text_similarity(str(a), str(b))


def calculate_confidence(items: List[Dict[str, Any]], field_weights: Optional[Dict[str, float]] = None) -> float:
    if not items:
        return 0.0
    if len(items) == 1:
        return 50.0

    all_keys = set()
    for item in items:
        if isinstance(item, dict):
            all_keys.update(item.keys())

    if not all_keys:
        return 0.0

    if field_weights is None:
        field_weights = {k: 1.0 for k in all_keys}

    field_confidences = {}
    for key in all_keys:
        values = [item.get(key) for item in items if isinstance(item, dict)]
        valid_values = [v for v in values if v is not None]
        if len(valid_values) <= 1:
            field_confidences[key] = 50.0
            continue

        pair_sims = []
        for i in range(len(valid_values)):
            for j in range(i + 1, len(valid_values)):
                sim = _value_similarity(valid_values[i], valid_values[j])
                pair_sims.append(sim)

        avg_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0
        field_confidences[key] = avg_sim * 100.0

    total_weight = 0.0
    weighted_sum = 0.0
    for key in all_keys:
        weight = field_weights.get(key, 1.0)
        conf = field_confidences.get(key, 0.0)
        weighted_sum += conf * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _get_field_confidences(items: List[Dict[str, Any]]) -> Dict[str, float]:
    if not items:
        return {}

    all_keys = set()
    for item in items:
        if isinstance(item, dict):
            all_keys.update(item.keys())

    field_confidences = {}
    for key in all_keys:
        values = [item.get(key) for item in items if isinstance(item, dict)]
        valid_values = [v for v in values if v is not None]
        if len(valid_values) <= 1:
            field_confidences[key] = 50.0
            continue

        pair_sims = []
        for i in range(len(valid_values)):
            for j in range(i + 1, len(valid_values)):
                sim = _value_similarity(valid_values[i], valid_values[j])
                pair_sims.append(sim)

        avg_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0
        field_confidences[key] = round(avg_sim * 100.0, 2)

    return field_confidences


def _find_majority_result(items: List[Dict[str, Any]], field_weights: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    if len(items) == 1:
        return items[0]

    best_idx = 0
    best_score = -1.0

    for i, item in enumerate(items):
        score = 0.0
        for j, other in enumerate(items):
            if i == j:
                continue
            all_keys = set()
            if isinstance(item, dict):
                all_keys.update(item.keys())
            if isinstance(other, dict):
                all_keys.update(other.keys())

            if not all_keys:
                continue

            if field_weights is None:
                field_w = {k: 1.0 for k in all_keys}
            else:
                field_w = field_weights

            total_w = 0.0
            weighted_sim = 0.0
            for key in all_keys:
                w = field_w.get(key, 1.0)
                sim = _value_similarity(item.get(key) if isinstance(item, dict) else None,
                                        other.get(key) if isinstance(other, dict) else None)
                weighted_sim += sim * w
                total_w += w

            avg_sim = weighted_sim / total_w if total_w > 0 else 0.0
            score += avg_sim

        if score > best_score:
            best_score = score
            best_idx = i

    return items[best_idx]


def aggregate_results(parsed_results: List[Dict[str, Any]], confidence: float,
                      confidence_threshold: float = 60.0,
                      field_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    if not parsed_results:
        return {
            "confidence": 0.0,
            "confidence_details": {},
            "low_confidence_fields": [],
            "num_samples": 0,
        }

    main_result = _find_majority_result(parsed_results, field_weights)
    field_details = _get_field_confidences(parsed_results)

    low_confidence_fields = [
        field for field, conf in field_details.items()
        if conf < confidence_threshold
    ]

    result = dict(main_result) if main_result else {}
    result["confidence"] = round(confidence, 2)
    result["confidence_details"] = field_details
    result["low_confidence_fields"] = low_confidence_fields
    result["num_samples"] = len(parsed_results)

    return result


class SelfConsistencyEngine:
    def __init__(self, llm_client, num_samples: int = 3,
                 temp_min: float = 0.1, temp_max: float = 0.5,
                 confidence_threshold: float = 60.0):
        self.llm_client = llm_client
        self.num_samples = max(1, num_samples)
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.confidence_threshold = confidence_threshold

    def _generate_temperatures(self) -> List[float]:
        if self.num_samples == 1:
            return [self.temp_min]
        temps = []
        for i in range(self.num_samples):
            t = self.temp_min + (self.temp_max - self.temp_min) * i / (self.num_samples - 1)
            temps.append(round(t, 3))
        return temps

    def run(self, messages: List[Dict[str, str]],
            parser_func: Callable[..., Optional[Any]],
            parser_args: Optional[tuple] = None,
            parser_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if parser_args is None:
            parser_args = ()
        if parser_kwargs is None:
            parser_kwargs = {}

        temperatures = self._generate_temperatures()
        raw_responses = []
        parsed_results = []

        for i, temp in enumerate(temperatures):
            logger.info(f"自洽性验证 - 采样 {i + 1}/{self.num_samples}, temperature={temp}")
            resp = self.llm_client.chat_completion(messages, temperature=temp)
            if resp is None:
                logger.warning(f"采样 {i + 1} 调用失败，已跳过")
                continue
            raw_responses.append(resp)
            try:
                parsed = parser_func(resp, *parser_args, **parser_kwargs)
                if parsed is not None:
                    parsed_results.append(parsed)
                else:
                    logger.warning(f"采样 {i + 1} 解析结果为空，已跳过")
            except Exception as e:
                logger.warning(f"采样 {i + 1} 解析异常: {e}，已跳过")

        logger.info(f"自洽性验证 - 有效结果 {len(parsed_results)}/{self.num_samples}")

        if not parsed_results:
            logger.error("自洽性验证 - 所有采样均失败")
            return {
                "confidence": 0.0,
                "confidence_details": {},
                "low_confidence_fields": [],
                "num_samples": 0,
                "success": False,
            }

        confidence = calculate_confidence(parsed_results)
        result = aggregate_results(parsed_results, confidence,
                                   confidence_threshold=self.confidence_threshold)
        result["success"] = True
        result["raw_responses_count"] = len(raw_responses)

        logger.info(f"自洽性验证 - 总体置信度: {confidence:.2f}%")
        return result
