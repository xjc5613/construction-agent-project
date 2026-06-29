# 分主题技术路线图模块 - 实施计划

## [x] Task 1: Prompt模板与消息构建器
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 创建 `prompt_templates/per_topic_roadmap_system.txt` - 系统prompt，定义角色、任务、输出格式要求
  - 创建 `prompt_templates/per_topic_roadmap_user.txt` - 用户prompt模板，包含主题信息占位符
  - 创建 `src/prompt_builder/per_topic_roadmap_builder.py` - 消息构建器函数
  - 输入：单个主题的round1结果（topic_name, bottlenecks, breakthroughs, fusion_topics, fusion_scenario等）
  - 输出：格式化的messages列表，包含系统消息和用户消息
  - 输出JSON格式要求：四个时间阶段（2025/2030/2035/2040），每阶段包含milestones数组，每个milestone含name, description, key_technologies, trl_level, dependencies, uncertainty_level
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-8
- **Test Requirements**:
  - `programmatic` TR-1.1: 能正确构建包含主题完整信息的messages
  - `programmatic` TR-1.2: prompt中包含所有必要的占位符和格式说明
  - `human-judgement` TR-1.3: prompt语言清晰，指令明确，角色设定合理
- **Notes**: 参考现有round1/round2/round3的prompt风格，保持一致性

## [x] Task 2: 输出解析器 - 路线图JSON解析
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 创建 `src/output_parser/parse_per_topic_roadmap.py` - 路线图输出解析器
  - 功能：从LLM原始响应中解析出结构化的路线图JSON
  - 支持多种格式：纯JSON、markdown代码块、带前后缀文本
  - 解析结果格式：
    ```python
    {
        "topic_name": "主题名称",
        "roadmap": {
            "2025": {
                "stage_description": "阶段描述",
                "milestones": [
                    {
                        "name": "里程碑名称",
                        "description": "详细描述",
                        "key_technologies": ["技术1", "技术2"],
                        "trl_level": 3,
                        "dependencies": ["依赖的前置技术"],
                        "uncertainty_level": "low|medium|high"
                    }
                ]
            },
            "2030": {...},
            "2035": {...},
            "2040": {...}
        }
    }
    ```
  - 提供健壮的错误处理和降级机制
- **Acceptance Criteria Addressed**: AC-2, AC-8
- **Test Requirements**:
  - `programmatic` TR-2.1: 能正确解析标准JSON格式输出
  - `programmatic` TR-2.2: 能正确解析markdown代码块包裹的JSON
  - `programmatic` TR-2.3: 能处理部分损坏的JSON（尝试修复）
  - `programmatic` TR-2.4: 解析结果符合schema，字段完整
  - `programmatic` TR-2.5: 空输入/格式错误时返回空字典而非抛出异常
- **Notes**: 参考现有parse_round1.py和parse_round3.py的实现风格

## [x] Task 3: LLM编排器 - 单主题路线图生成
- **Priority**: high
- **Depends On**: Task 1, Task 2
- **Description**:
  - 创建 `src/llm_orchestrator/per_topic_roadmap_runner.py` - 单主题路线图运行器
  - 功能：对单个主题调用LLM生成路线图并解析结果
  - 支持现有增强功能：自洽性验证、多模型集成、多Agent辩论（跟随全局配置）
  - 支持缓存：每个主题单独缓存，文件名为 `per_topic_roadmap_{topic_name}.json`
  - 提供函数 `run_per_topic_roadmap(topic_data, force_rerun=False) -> Dict`
- **Acceptance Criteria Addressed**: AC-1, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` TR-3.1: 能正确调用LLM并解析返回结果（使用mock测试）
  - `programmatic` TR-3.2: 缓存机制正常工作（force_rerun=False时读取缓存）
  - `programmatic` TR-3.3: force_rerun=True时忽略缓存重新生成
  - `programmatic` TR-3.4: 与自洽性验证/多Agent辩论等增强功能兼容
- **Notes**: 参考round3_runner.py的实现结构

## [x] Task 4: 批量Runner - 多主题批量处理
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - 在 `src/llm_orchestrator/per_topic_roadmap_runner.py` 中增加批量处理函数
  - 提供函数 `run_all_topics_roadmap(round1_results, force_rerun=False) -> List[Dict]`
  - 功能：遍历所有主题，逐个生成路线图，汇总结果
  - 进度日志：每个主题开始/完成时打印日志
  - 错误处理：单个主题失败不影响其他主题，记录失败日志
  - 保存汇总结果到 `parsed/per_topic_roadmaps_all.json`
- **Acceptance Criteria Addressed**: AC-1, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` TR-4.1: 能正确处理多个主题的批量生成（mock测试）
  - `programmatic` TR-4.2: 单个主题失败时不中断整体流程
  - `programmatic` TR-4.3: 结果汇总格式正确，包含所有成功生成的主题
  - `programmatic` TR-4.4: 汇总文件正确保存到指定路径
- **Notes**: 处理主题名称中的特殊字符（如中文、空格），确保文件名安全

## [x] Task 5: Markdown报告生成器 - 时间轴与流程图
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - 创建 `src/report/per_topic_roadmap_report.py` - 分主题路线图报告生成器
  - 功能1：为单个主题生成Markdown报告，包含：
    - 主题概述
    - 时间轴视图（Mermaid timeline语法）
    - 流程图视图（Mermaid flowchart TD语法，展示技术演进和依赖）
    - 分阶段详细里程碑表格
  - 功能2：生成整合报告，包含所有主题的索引和各自的路线图
  - Mermaid时间轴格式示例：
    ```
    timeline
        title 技术发展路线图
        2025 : 里程碑A : 里程碑B
        2030 : 里程碑C : 里程碑D
    ```
  - Mermaid流程图格式示例：
    ```
    flowchart TD
        A[2025: 基础技术] --> B[2030: 技术突破]
        B --> C[2035: 广泛应用]
        C --> D[2040: 成熟完善]
    ```
  - 报告保存到 `outputs/final_report/per_topic_roadmaps/` 目录
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-6
- **Test Requirements**:
  - `programmatic` TR-5.1: 能生成单个主题的Markdown报告
  - `programmatic` TR-5.2: Mermaid时间轴语法正确
  - `programmatic` TR-5.3: Mermaid流程图语法正确
  - `programmatic` TR-5.4: 能生成包含所有主题的整合报告
  - `human-judgement` TR-5.5: 报告结构清晰，视觉效果良好
- **Notes**: 流程图中体现依赖关系（dependencies字段），用箭头连接有依赖的里程碑

## [x] Task 6: 与主流程集成 + 配置项
- **Priority**: medium
- **Depends On**: Task 4, Task 5
- **Description**:
  - 在 `config/settings.py` 中新增配置项：
    - `ENABLE_PER_TOPIC_ROADMAP` - 是否生成分主题路线图（默认True）
    - `PER_TOPIC_ROADMAP_STAGES` - 时间阶段列表（默认["2025", "2030", "2035", "2040"]）
  - 在 `src/main.py` 中集成分主题路线图生成步骤
  - 在最终报告中增加"分主题技术路线图"章节（或链接到单独报告）
  - 确保该模块可独立运行（提供单独的入口脚本）
- **Acceptance Criteria Addressed**: AC-6, AC-7
- **Test Requirements**:
  - `programmatic` TR-6.1: 配置项正确定义并可通过环境变量覆盖
  - `programmatic` TR-6.2: 关闭功能时主流程不受影响
  - `programmatic` TR-6.3: 开启功能时主流程正确调用分主题路线图模块
  - `programmatic` TR-6.4: 提供独立运行入口脚本
- **Notes**: 默认开启该功能，与现有流程无缝集成

## [x] Task 7: 集成测试与验证
- **Priority**: medium
- **Depends On**: Task 6
- **Description**:
  - 端到端测试：使用mock数据跑通完整流程
  - 验证所有9个主题的路线图生成
  - 验证报告生成和文件输出
  - 验证与现有增强功能（自洽性、辩论等）的兼容性
  - 新增测试文件：`tests/test_per_topic_roadmap.py`
  - 确保所有现有测试仍然通过（无回归）
- **Acceptance Criteria Addressed**: AC-1, AC-5, AC-7, AC-8
- **Test Requirements**:
  - `programmatic` TR-7.1: 端到端流程测试通过（mock API）
  - `programmatic` TR-7.2: 所有现有测试通过（无回归）
  - `programmatic` TR-7.3: 新增测试覆盖所有核心功能
  - `human-judgement` TR-7.4: 生成的示例报告质量良好，图形化展示有效
- **Notes**: 测试总数预计增加20-30个
