# -*- coding:utf-8-*-
from typing import List, Dict, Any, Optional, Callable
from src.utils.logger import get_logger
from .self_consistency import (
    calculate_confidence,
    _value_similarity,
    _get_field_confidences,
    _find_majority_result,
    aggregate_results,
)

logger = get_logger(__name__)


class EnsembleEngine:
    def __init__(self, multi_model_client, parser_func: Callable,
                 strategy: str = "weighted_vote",
                 confidence_threshold: float = 60.0):
        self.multi_model_client = multi_model_client
        self.parser_func = parser_func
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold

    def _parse_results(self, raw_results: List[Dict[str, Any]],
                       parser_args: tuple = None,
                       parser_kwargs: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if parser_args is None:
            parser_args = ()
        if parser_kwargs is None:
            parser_kwargs = {}

        parsed = []
        for item in raw_results:
            if not item.get("success") or item.get("content") is None:
                continue
            try:
                result = self.parser_func(item["content"], *parser_args, **parser_kwargs)
                if result is not None:
                    parsed.append({
                        "model_name": item["model_name"],
                        "parsed": result,
                        "raw": item["content"]
                    })
                else:
                    logger.warning(f"模型 {item['model_name']} 解析结果为空，已跳过")
            except Exception as e:
                logger.warning(f"模型 {item['model_name']} 解析异常: {e}，已跳过")
        return parsed

    def _weighted_vote_aggregate(self, parsed_items: List[Dict[str, Any]],
                                  weights: Dict[str, float]) -> Dict[str, Any]:
        if not parsed_items:
            return {}

        all_keys = set()
        for item in parsed_items:
            parsed = item.get("parsed", {})
            if isinstance(parsed, dict):
                all_keys.update(parsed.keys())

        if not all_keys:
            return {}

        result = {}
        for key in all_keys:
            values_with_weight = []
            for item in parsed_items:
                parsed = item.get("parsed", {})
                if isinstance(parsed, dict) and key in parsed:
                    model_name = item["model_name"]
                    weight = weights.get(model_name, 1.0 / len(parsed_items))
                    values_with_weight.append((parsed[key], weight))

            if not values_with_weight:
                continue

            best_val = None
            best_score = -1.0

            for val, w in values_with_weight:
                score = 0.0
                for other_val, other_w in values_with_weight:
                    sim = _value_similarity(val, other_val)
                    score += sim * other_w
                if score > best_score:
                    best_score = score
                    best_val = val

            result[key] = best_val

        return result

    def _majority_vote_aggregate(self, parsed_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not parsed_items:
            return {}

        all_keys = set()
        for item in parsed_items:
            parsed = item.get("parsed", {})
            if isinstance(parsed, dict):
                all_keys.update(parsed.keys())

        if not all_keys:
            return {}

        n = len(parsed_items)
        majority_threshold = n / 2.0

        result = {}
        for key in all_keys:
            values = []
            for item in parsed_items:
                parsed = item.get("parsed", {})
                if isinstance(parsed, dict) and key in parsed:
                    values.append(parsed[key])

            if not values:
                continue

            best_val = None
            best_count = 0

            for i, val in enumerate(values):
                count = 0
                for other_val in values:
                    sim = _value_similarity(val, other_val)
                    if sim > 0.6:
                        count += 1
                if count > best_count:
                    best_count = count
                    best_val = val

            if best_count > majority_threshold:
                result[key] = best_val

        return result

    def _consensus_aggregate(self, parsed_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not parsed_items:
            return {}

        all_keys = set()
        for item in parsed_items:
            parsed = item.get("parsed", {})
            if isinstance(parsed, dict):
                all_keys.update(parsed.keys())

        if not all_keys:
            return {}

        result = {}
        for key in all_keys:
            values = []
            for item in parsed_items:
                parsed = item.get("parsed", {})
                if isinstance(parsed, dict) and key in parsed:
                    values.append(parsed[key])

            if len(values) < len(parsed_items):
                continue

            all_same = True
            first_val = values[0]
            for val in values[1:]:
                sim = _value_similarity(first_val, val)
                if sim < 0.9:
                    all_same = False
                    break

            if all_same:
                result[key] = first_val

        return result

    def _compute_model_consensus(self, parsed_items: List[Dict[str, Any]],
                                  main_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        consensus = []
        for item in parsed_items:
            model_name = item["model_name"]
            parsed = item.get("parsed", {})
            field_sims = {}
            if isinstance(parsed, dict):
                for key, val in parsed.items():
                    if key in main_result:
                        field_sims[key] = round(_value_similarity(val, main_result[key]) * 100, 2)
            consensus.append({
                "model_name": model_name,
                "field_similarities": field_sims
            })
        return consensus

    def run(self, messages: List[Dict[str, str]],
            parser_args: tuple = None,
            parser_kwargs: Dict[str, Any] = None) -> Dict[str, Any]:
        if parser_args is None:
            parser_args = ()
        if parser_kwargs is None:
            parser_kwargs = {}

        logger.info(f"多模型集成 - 策略: {self.strategy}")
        multi_result = self.multi_model_client.chat_completion(messages)
        raw_results = multi_result.get("results", [])

        parsed_items = self._parse_results(raw_results, parser_args, parser_kwargs)
        success_models = [item["model_name"] for item in parsed_items]
        failed_models = [
            r["model_name"] for r in raw_results
            if not r.get("success") or r.get("content") is None
        ]

        logger.info(f"多模型集成 - 有效模型 {len(parsed_items)}/{multi_result.get('model_count', 0)}")
        if failed_models:
            logger.warning(f"失败模型: {failed_models}")

        if not parsed_items:
            logger.error("多模型集成 - 所有模型均失败")
            return {
                "confidence": 0.0,
                "confidence_details": {},
                "low_confidence_fields": [],
                "num_models": 0,
                "success_models": [],
                "failed_models": failed_models,
                "model_consensus": [],
                "success": False,
            }

        parsed_dicts = [item["parsed"] for item in parsed_items
                        if isinstance(item.get("parsed"), dict)]

        weights = {}
        if hasattr(self.multi_model_client, 'get_normalized_weights'):
            weights = self.multi_model_client.get_normalized_weights(success_models)
        else:
            count = len(success_models)
            weights = {name: 1.0 / count for name in success_models}

        if self.strategy == "weighted_vote":
            aggregated = self._weighted_vote_aggregate(parsed_items, weights)
        elif self.strategy == "majority_vote":
            aggregated = self._majority_vote_aggregate(parsed_items)
        elif self.strategy == "consensus":
            aggregated = self._consensus_aggregate(parsed_items)
        else:
            logger.warning(f"未知策略 {self.strategy}，使用 weighted_vote")
            aggregated = self._weighted_vote_aggregate(parsed_items, weights)

        if parsed_dicts:
            overall_confidence = calculate_confidence(parsed_dicts)
            field_confidences = _get_field_confidences(parsed_dicts)
        else:
            overall_confidence = 0.0
            field_confidences = {}

        if self.strategy == "consensus" and not aggregated:
            overall_confidence = min(overall_confidence, 30.0)

        low_confidence_fields = [
            field for field, conf in field_confidences.items()
            if conf < self.confidence_threshold
        ]

        model_consensus = self._compute_model_consensus(parsed_items, aggregated)

        result = dict(aggregated)
        result["confidence"] = round(overall_confidence, 2)
        result["confidence_details"] = field_confidences
        result["low_confidence_fields"] = low_confidence_fields
        result["num_models"] = len(parsed_items)
        result["success_models"] = success_models
        result["failed_models"] = failed_models
        result["model_consensus"] = model_consensus
        result["strategy"] = self.strategy
        result["success"] = True

        logger.info(f"多模型集成 - 总体置信度: {overall_confidence:.2f}%")
        return result
