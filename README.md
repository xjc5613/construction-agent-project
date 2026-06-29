# 智能建造2040技术预测系统

基于大语言模型，对智能建造领域的9个核心技术主题进行2030-2040年技术趋势预测。系统采用多轮迭代预测方法，结合自洽性验证、多模型集成、多Agent辩论等机制，提升预测结果的可靠性和准确性。

## 功能特性

### 核心预测功能
- **技术主题演化预测**：针对9个智能建造技术主题，分析2030-2035年发展瓶颈和2040年技术突破方向
- **新范式识别**：综合提炼智能建造领域的新范式
- **技术路线图**：生成分阶段技术发展路线图（2030/2035/2040）

### 增强功能

#### 1. 自洽性验证 (Self-Consistency)
对同一问题进行多次采样，通过结果一致性计算置信度，有效降低模型随机性带来的误差。
- 可配置采样数量和温度范围
- 字段级置信度计算
- 自动识别低置信度项

#### 2. 多模型集成 (Multi-Model Ensemble)
集成多个大语言模型的预测结果，通过投票机制提升预测稳健性。
- 支持加权投票、多数投票、共识等多种策略
- 模型间一致性分析
- 自动处理模型失败情况

#### 3. 多Agent辩论 (Multi-Agent Debate)
多角色专家（技术专家、产业分析师、风险评估师、方法论专家）对预测结果进行多轮评审和辩论。
- 可配置Agent角色和辩论轮数
- 自动修正预测结果
- 生成辩论摘要

#### 4. 推理链条 (Reasoning Chain)
追踪预测结论的推理过程，提供透明可追溯的依据。
- 逐步展示推理逻辑
- 自动标注证据来源（IPC分类、融合对、主题提及等）
- 计算依据充分度评分

#### 5. 路线图增强 (Roadmap Enhanced)
技术路线图增加TRL等级、影响范围、不确定性等维度。
- 技术成熟度（TRL 1-9级）
- 影响范围（局部/行业级/全局）
- 不确定性等级（低/中/高）
- 依赖关系标注

#### 6. 回溯验证 (Backtesting)
基于历史数据验证预测方法的有效性。
- 可配置历史回溯年份
- 预测准确度评估

## 安装

```bash
pip install -r requirements.txt
```

## 配置

### 环境变量

复制 `.env.example` 为 `.env` 并配置相关参数：

```bash
cp .env.example .env
```

### 核心配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API 基础地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 使用的模型名称 |
| `TEMPERATURE` | `0.15` | 生成温度 |
| `MAX_TOKENS` | `2048` | 最大生成token数 |

### 功能开关配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ENABLE_SELF_CONSISTENCY` | `false` | 启用自洽性验证 |
| `ENABLE_MULTI_MODEL` | `false` | 启用多模型集成 |
| `ENABLE_MULTI_AGENT_DEBATE` | `false` | 启用多Agent辩论 |
| `ENABLE_REASONING_CHAIN` | `false` | 启用推理链条追踪 |
| `ENABLE_ROADMAP_ENHANCED` | `false` | 启用路线图增强字段 |

### 自洽性验证配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `SELF_CONSISTENCY_SAMPLES` | `3` | 采样数量 |
| `SELF_CONSISTENCY_TEMPERATURE_MIN` | `0.1` | 最小温度 |
| `SELF_CONSISTENCY_TEMPERATURE_MAX` | `0.5` | 最大温度 |
| `CONFIDENCE_THRESHOLD` | `60` | 置信度阈值（百分比） |

### 多模型集成配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MULTI_MODEL_LIST` | `[]` | 模型配置列表（JSON格式） |
| `MULTI_MODEL_STRATEGY` | `weighted_vote` | 集成策略：weighted_vote/majority_vote/consensus |

### 多Agent辩论配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEBATE_ROUNDS` | `2` | 辩论轮数 |
| `DEBATE_AGENTS` | `["tech_expert","industry_analyst","risk_assessor"]` | Agent角色列表 |

### 回溯验证配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `BACKTEST_HISTORICAL_YEAR` | `2020` | 历史回溯年份 |

## 使用方法

### 快速开始

```bash
python -m src.main
```

### 强制重新运行（忽略缓存）

```python
from src.llm_orchestrator import run_round1, run_round2, run_round3

# 强制重新运行，忽略缓存
round1_results = run_round1(topic_inputs, force_rerun=True)
```

### 启用自洽性验证

在 `.env` 中设置：
```
ENABLE_SELF_CONSISTENCY=true
SELF_CONSISTENCY_SAMPLES=5
```

### 启用多模型集成

在 `.env` 中设置：
```
ENABLE_MULTI_MODEL=true
MULTI_MODEL_LIST=[{"model": "deepseek-chat", "weight": 0.5}, {"model": "other-model", "weight": 0.5}]
MULTI_MODEL_STRATEGY=weighted_vote
```

### 启用多Agent辩论

在 `.env` 中设置：
```
ENABLE_MULTI_AGENT_DEBATE=true
DEBATE_ROUNDS=3
DEBATE_AGENTS=["tech_expert","industry_analyst","risk_assessor","methodology_expert"]
```

### 启用推理链条

在 `.env` 中设置：
```
ENABLE_REASONING_CHAIN=true
```

### 启用路线图增强

在 `.env` 中设置：
```
ENABLE_ROADMAP_ENHANCED=true
```

## 输出说明

运行完成后，输出文件位于 `outputs/` 目录：

```
outputs/
├── raw/                    # 原始API响应
├── parsed/                 # 解析后的结构化数据
└── final_report/
    └── forecast_report.md  # 最终预测报告
```

### 报告结构

1. **技术主题演化预测**：每个主题的瓶颈、突破、融合场景、置信度标注
2. **智能建造新范式**：综合提炼的新范式名称和描述
3. **技术路线图**：分阶段技术路线（含TRL、影响范围、不确定性）
4. **不确定性分析**：低置信度项汇总、关键假设、方法局限性
5. **方法说明**：预测方法论、置信度评估方式、技术工具与数据来源
6. **附录：推理链条**：关键结论的推理过程、核心依据来源

## 置信度说明

| 等级 | 阈值 | 含义 |
|------|------|------|
| 🟢 高置信 | ≥80% | 预测结果一致性高，可靠性强 |
| 🟡 中置信 | 60%-79% | 预测结果基本一致，存在一定不确定性 |
| 🔴 低置信 | <60% | 预测结果分歧较大，需谨慎参考 |

## 测试

### 运行所有测试

```bash
# 方式1：运行所有测试文件
python3 -m pytest tests/ -v

# 方式2：各测试文件独立运行
python3 tests/test_report_generator.py
python3 tests/test_integration.py
python3 tests/test_self_consistency.py
python3 tests/test_ensemble.py
python3 tests/test_debate.py
python3 tests/test_reasoning_chain.py
python3 tests/test_backtesting.py
python3 tests/test_parse_round1.py
python3 tests/test_parse_round3.py
python3 tests/test_settings.py
```

### 测试覆盖范围

- 报告生成器测试（置信度、证据、路线图、推理链条、向后兼容）
- 集成测试（端到端流程、各功能开关、缓存机制）
- 自洽性验证测试
- 多模型集成测试
- 多Agent辩论测试
- 推理链条测试
- 回溯验证测试
- 输出解析器测试
- 配置设置测试

## 最佳实践

### 1. 渐进式启用增强功能
建议先使用默认配置运行，然后逐步启用增强功能：
1. 先启用 `ENABLE_REASONING_CHAIN`（不增加API调用）
2. 再启用 `ENABLE_SELF_CONSISTENCY`（增加N倍API调用）
3. 最后启用 `ENABLE_MULTI_AGENT_DEBATE`（增加多轮API调用）

### 2. 合理设置自洽性采样数
- 快速验证：2-3个样本
- 正式预测：3-5个样本
- 样本数超过5个收益递减

### 3. 利用缓存机制
系统默认缓存解析结果，可通过 `force_rerun=True` 强制重新运行。建议在调试时利用缓存提高效率。

### 4. 关注低置信度项
报告中的高不确定性项（⚠️标记）需要重点关注，可能需要人工复核或补充数据。

### 5. 多模型集成注意事项
- 确保模型列表中的模型都有可用的API密钥
- 加权投票策略可根据各模型表现调整权重
- 模型数量建议2-4个，过多会增加成本且收益有限

## 项目结构

```
construction-agent-project/
├── config/                     # 配置模块
│   ├── settings.py             # 全局设置
│   └── prompt_templates/       # 提示词模板
├── data/                       # 数据目录
│   └── raw/                    # 原始数据
├── src/                        # 源代码
│   ├── main.py                 # 主入口
│   ├── report_generator.py     # 报告生成器
│   ├── data_preparation/       # 数据准备
│   ├── llm_orchestrator/       # LLM编排（自洽性/集成/辩论）
│   ├── output_parser/          # 输出解析
│   ├── prompt_builder/         # 提示词构建
│   ├── evaluation/             # 评估（回溯验证）
│   └── utils/                  # 工具函数
├── tests/                      # 测试文件
├── requirements.txt            # 依赖包
└── README.md                   # 项目说明
```

## 技术主题

系统覆盖以下9个智能建造核心技术主题：

1. 多专业协同平台
2. 参数化与生成式设计
3. 机器人集群协同
4. 施工全过程数字孪生
5. 智能规范审查
6. 建筑工程大模型技术
7. 装配式建筑技术
8. 建筑规模增材制造
9. 模块化与可重构设计

## 许可证

本项目仅供研究和学习使用。
