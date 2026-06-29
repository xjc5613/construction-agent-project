# 智能建造2040技术预测Agent优化 - 实施计划

## [x] Task 1: 修复已知Bug与代码健壮性提升
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 修复 [parse_round1.py](file:///Users/bytedance/construction-agent-project/src/output_parser/parse_round1.py#L62) 中 `filter_unrealistic_breakthroughs` 调用参数错误问题
  - 增加函数签名类型检查和边界情况处理
  - 增强JSON解析的健壮性，支持更多格式变体
  - 增加单元测试验证修复效果
- **Acceptance Criteria Addressed**: AC-6, AC-10
- **Test Requirements**:
  - `programmatic` TR-1.1: 传入包含禁忌词的breakthroughs列表，验证过滤后列表不包含禁忌词
  - `programmatic` TR-1.2: 调用parse_round1_output处理各种格式的LLM响应（纯JSON、带markdown、带前后缀文本），均能正确解析
  - `programmatic` TR-1.3: 现有测试用例全部通过，无回归问题
- **Notes**: 此任务为基础修复，需最先完成以确保后续优化的代码基础可靠

## [x] Task 2: 配置系统增强 - 支持灵活配置预测参数
- **Priority**: high
- **Depends On**: Task 1
- **Description**: 
  - 扩展 [settings.py](file:///Users/bytedance/construction-agent-project/config/settings.py)，增加新功能的配置项
  - 新增配置项：自洽性采样次数、多模型列表、多Agent角色配置、功能开关、置信度阈值等
  - 所有配置项均提供合理默认值，确保向后兼容
  - 支持通过环境变量覆盖配置
- **Acceptance Criteria Addressed**: AC-9, AC-10
- **Test Requirements**:
  - `programmatic` TR-2.1: 修改配置文件中采样次数后，系统按新值运行
  - `programmatic` TR-2.2: 禁用所有新功能开关后，系统行为与原版本一致
  - `programmatic` TR-2.3: 环境变量可正确覆盖配置文件中的默认值
- **Notes**: 配置系统是后续功能的基础，需提前设计好配置结构

## [x] Task 3: 自洽性验证模块 - Self-Consistency采样与投票
- **Priority**: high
- **Depends On**: Task 2
- **Description**: 
  - 在 `src/llm_orchestrator/` 下新增 `self_consistency.py` 模块
  - 实现多次独立采样功能：对同一问题用不同temperature或prompt变体调用N次
  - 实现投票/聚类算法：对结构化输出字段计算一致性得分
  - 实现置信度计算：基于投票集中度、选项分布熵计算0-100置信度
  - 集成到round1/round2/round3 runner中，可配置启用
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-3.1: 设置采样次数N=5，验证实际调用次数为5次
  - `programmatic` TR-3.2: 对于完全一致的5次输出，置信度应为95+
  - `programmatic` TR-3.3: 对于分歧较大的输出，置信度应低于50
  - `programmatic` TR-3.4: 输出结果中包含confidence字段，且数值在0-100之间
- **Notes**: 自洽性是提升可靠性的核心机制，需确保算法合理且高效

## [x] Task 4: 多模型集成框架 - Multi-Model Ensemble
- **Priority**: high
- **Depends On**: Task 3
- **Description**: 
  - 扩展 [api_client.py](file:///Users/bytedance/construction-agent-project/src/utils/api_client.py)，支持多模型配置
  - 实现模型注册机制：可配置多个模型端点及其权重
  - 实现集成投票策略：加权投票、一致性计算、分歧检测
  - 新增 `src/llm_orchestrator/ensemble.py` 模块封装集成逻辑
  - 失败降级：某模型不可用时自动剔除并重新加权
- **Acceptance Criteria Addressed**: AC-3, AC-6
- **Test Requirements**:
  - `programmatic` TR-4.1: 配置2个以上模型时，系统能正确调用并集成结果
  - `programmatic` TR-4.2: 单模型配置下，系统行为与原版本一致（无额外开销）
  - `programmatic` TR-4.3: 某模型调用失败时，系统自动降级使用剩余模型
  - `programmatic` TR-4.4: 输出包含各模型的一致性分析数据
- **Notes**: 可先用模拟/测试模式验证逻辑，再接入真实多模型

## [x] Task 5: 多Agent辩论评审机制 - Multi-Agent Debate
- **Priority**: high
- **Depends On**: Task 3
- **Description**: 
  - 新增 `src/llm_orchestrator/debate.py` 模块
  - 定义多个Agent角色：技术专家（关注技术可行性）、产业分析师（关注产业化路径）、风险评估师（关注风险与不确定性）、方法论专家（关注预测方法论）
  - 实现多轮辩论流程：初始预测→各Agent评审质疑→修正完善→收敛共识
  - 生成辩论摘要，记录关键争议点和最终共识依据
  - 可配置辩论轮次和参与角色
- **Acceptance Criteria Addressed**: AC-1, AC-4
- **Test Requirements**:
  - `programmatic` TR-5.1: 启用辩论模式后，系统正确调用多轮对话
  - `programmatic` TR-5.2: 输出包含辩论摘要字段，记录关键讨论点
  - `human-judgement` TR-5.3: 辩论后的结果比初始预测更全面、考虑了更多维度
  - `programmatic` TR-5.4: 禁用辩论模式时，系统无额外调用开销
- **Notes**: 辩论机制是最能体现"融合模型与大语言模型协同优化"思路的功能

## [x] Task 6: 推理链条与可解释性增强
- **Priority**: medium
- **Depends On**: Task 5
- **Description**: 
  - 优化Prompt模板，要求LLM输出结构化推理过程
  - 在输出数据结构中增加 `reasoning_chain` 字段，记录：输入依据→推理步骤→结论
  - 实现依据来源自动标注：追溯到具体IPC分类号、融合对、样本摘要
  - 增加依据充分度评估：统计每项结论的支撑依据数量和质量
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic` TR-6.1: 输出JSON中包含reasoning_chain字段且格式正确
  - `programmatic` TR-6.2: 每项核心结论至少关联1条以上依据来源
  - `human-judgement` TR-6.3: 推理链条逻辑连贯，依据与结论有明确因果关系
- **Notes**: 可解释性是学术研究场景的重要需求

## [x] Task 7: 增强路线图解析与多维度分类
- **Priority**: medium
- **Depends On**: Task 1
- **Description**: 
  - 重写 [parse_round3.py](file:///Users/bytedance/construction-agent-project/src/output_parser/parse_round3.py) 解析逻辑
  - 增加分类维度：技术成熟度（TRL分级）、影响范围（局部/行业/全局）、不确定性等级（低/中/高）、依赖条件
  - 优化Prompt引导LLM按结构化格式输出
  - 增加时间节点合理性校验（如2030的技术不应比2040更先进）
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `programmatic` TR-7.1: 解析结果包含year, category, description, trl, impact_scope, uncertainty_level等字段
  - `programmatic` TR-7.2: 年份仅出现2030/2035/2040三个时间点
  - `programmatic` TR-7.3: 时间序列合理性校验通过（无明显逻辑矛盾）
- **Notes**: 路线图是最终报告的核心产出之一，提升其结构化程度很有价值

## [x] Task 8: 回溯验证模块 - Backtesting
- **Priority**: medium
- **Depends On**: Task 3
- **Description**: 
  - 新增 `src/evaluation/` 目录和 `backtesting.py` 模块
  - 实现时间回溯模拟：将数据"回退"到某个历史时间点，用当时可用信息做预测
  - 实现预测效果评估：与实际后续发展对比，计算准确率、时间偏差等指标
  - 提供验证报告生成功能
  - 支持模拟数据注入（因可能缺少真实历史标注数据）
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `programmatic` TR-8.1: 回溯验证模块能正确运行并输出评估指标
  - `programmatic` TR-8.2: 评估报告包含准确率、召回率、时间偏差等关键指标
  - `programmatic` TR-8.3: 使用模拟数据可完整走通验证流程
- **Notes**: 此功能在真实历史数据不足时，可作为方法论验证工具

## [x] Task 9: 增强报告生成 - 置信度可视化与不确定性分析
- **Priority**: medium
- **Depends On**: Task 6, Task 7
- **Description**: 
  - 增强 [report_generator.py](file:///Users/bytedance/construction-agent-project/src/report_generator.py)
  - 增加置信度标注：高/中/低置信度项用不同标记区分
  - 新增"不确定性分析"章节：汇总高不确定性项和关键假设
  - 新增"方法说明"章节：描述预测方法论和可信度评估方式
  - 新增"推理链条"附录：展示关键结论的完整推理过程
- **Acceptance Criteria Addressed**: AC-8
- **Test Requirements**:
  - `programmatic` TR-9.1: 生成的报告包含新增的章节和内容
  - `human-judgement` TR-9.2: 报告结构清晰，置信度标识直观易懂
  - `programmatic` TR-9.3: 所有新增内容都有对应数据来源，非空值
- **Notes**: 报告是用户直接接触的最终产出，质量提升感知最明显

## [x] Task 10: 集成测试与文档完善
- **Priority**: high
- **Depends On**: Task 1-9
- **Description**: 
  - 端到端集成测试：验证完整流程在各种配置组合下正常运行
  - 性能测试：评估不同配置下的API调用次数和耗时
  - 回归测试：确保原有功能不受影响
  - 更新README文档，说明新功能和配置方法
  - 编写使用示例和最佳实践建议
- **Acceptance Criteria Addressed**: AC-10, AC-9
- **Test Requirements**:
  - `programmatic` TR-10.1: 默认配置下完整流程运行成功，输出与旧版兼容
  - `programmatic` TR-10.2: 全功能开启配置下完整流程运行成功
  - `programmatic` TR-10.3: 各功能模块独立开关均正常工作
  - `human-judgement` TR-10.4: 文档清晰说明了新功能的使用方法和配置方式
- **Notes**: 此任务确保整体交付质量
