# 分主题技术路线图模块 - 产品需求文档

## Overview
- **Summary**: 为智能建造2040技术预测系统新增"分主题技术路线图"核心模块，对9个技术主题分别生成独立的、分阶段（2025-2030-2035-2040）的技术发展路线图，包含时间轴视图和流程图视图，展示每个主题的技术演进路径、关键里程碑、依赖关系和成熟度变化。
- **Purpose**: 解决当前系统只有全局综合路线图、缺乏各主题独立发展路径的问题，使用户能够深入了解每个技术主题的详细发展脉络，增强预测结果的可操作性和颗粒度。
- **Target Users**: 技术战略规划人员、研发管理者、行业分析师、投资决策者

## Goals
- 为9个技术主题分别生成独立完整的技术路线图
- 支持时间轴形式展示（2025→2030→2035→2040四阶段）
- 支持流程图形式展示技术演进路径与依赖关系
- 每条路线图条目包含多维度属性（TRL等级、关键技术、里程碑、依赖、不确定性）
- 与现有全局路线图形成互补，不破坏现有功能
- 生成可视化的Markdown报告，包含图形化展示

## Non-Goals (Out of Scope)
- 不生成交互式Web前端页面（仅Markdown/JSON输出）
- 不涉及真实的甘特图或Project文件导出
- 不改变现有的三轮预测架构（新增为第四轮/附加模块）
- 不做跨主题的路线图交叉依赖分析（后续迭代可加）
- 不做动态时间轴（固定为2025/2030/2035/2040四个时间节点）

## Background & Context
- 现有系统第一轮（round1）已对9个主题进行了深度分析，包含瓶颈、突破、融合场景等信息
- 现有第三轮（round3）生成全局综合路线图，共11条里程碑，但未按主题拆分
- 每个主题的发展路径信息分散在bottlenecks和breakthroughs中，缺乏结构化的时间维度拆解
- 用户需要更细粒度的主题级路线图，用于指导具体技术领域的规划
- 参考融合模型与大语言模型协同优化的思路，可基于第一轮结果进行二次推理生成路线图

## Functional Requirements
- **FR-1**: 基于第一轮每个主题的预测结果，生成该主题独立的技术路线图（2025/2030/2035/2040四阶段）
- **FR-2**: 每条路线图条目包含：时间节点、里程碑名称、详细描述、关键技术、TRL等级、依赖项、不确定性等级
- **FR-3**: 支持时间轴形式的Markdown可视化展示（Mermaid时间轴语法）
- **FR-4**: 支持流程图形式的Markdown可视化展示（Mermaid流程图语法，展示技术演进路径与依赖）
- **FR-5**: 每个主题路线图包含：现状分析（2025）、近期突破（2030）、中期成熟（2035）、远期愿景（2040）
- **FR-6**: 提供统一的Runner入口函数，可批量处理所有主题
- **FR-7**: 支持缓存机制，避免重复调用API
- **FR-8**: 生成整合报告，包含所有主题的路线图汇总与索引
- **FR-9**: 与现有增强功能兼容（自洽性验证、多Agent辩论、推理链条等）

## Non-Functional Requirements
- **NFR-1**: 每个主题路线图生成时间 < 30秒（不含API等待时间）
- **NFR-2**: JSON输出格式严格遵守schema，便于后续程序化处理
- **NFR-3**: Markdown报告渲染正常，Mermaid图形在支持的查看器中可正确显示
- **NFR-4**: 代码模块化，便于后续扩展（如增加更多时间节点或维度）
- **NFR-5**: 向后兼容，不影响现有三轮预测的正常运行

## Constraints
- **Technical**: Python 3.x，基于现有项目架构（prompt_builder + llm_orchestrator + output_parser + report_generator）
- **Business**: 需调用LLM API，有一定成本；9个主题各调用1次，总计增加9次API调用
- **Dependencies**: 依赖第一轮（round1）的输出结果作为输入；使用现有LLMClient；使用Mermaid语法做可视化（无需额外依赖）

## Assumptions
- 第一轮每个主题已有足够的信息（瓶颈、突破、融合场景等）支撑路线图生成
- LLM能够基于主题分析结果推导出分阶段的技术发展路径
- Mermaid语法的Markdown报告是可接受的可视化形式
- 4个时间节点（2025/2030/2035/2040）足以覆盖技术发展脉络

## Acceptance Criteria

### AC-1: 分主题路线图生成
- **Given**: 已有第一轮9个主题的预测结果
- **When**: 调用分主题路线图生成模块
- **Then**: 为每个主题生成独立的路线图JSON文件，包含至少4个时间节点、每节点至少2条里程碑
- **Verification**: `programmatic`
- **Notes**: 9个主题 × 4个时间节点 × ≥2条里程碑 = ≥72条路线图条目

### AC-2: 路线图条目多维度属性
- **Given**: 单个主题的路线图结果
- **When**: 检查每条路线图条目
- **Then**: 每条条目包含：time_stage, milestone, description, key_technologies, trl_level, dependencies, uncertainty_level 字段
- **Verification**: `programmatic`

### AC-3: 时间轴可视化
- **Given**: 单个主题的路线图数据
- **When**: 生成Markdown报告
- **Then**: 包含Mermaid时间轴图形（timeline语法），按时间节点展示里程碑
- **Verification**: `human-judgment`
- **Notes**: Mermaid语法需正确，在支持的Markdown查看器中可渲染

### AC-4: 流程图可视化
- **Given**: 单个主题的路线图数据
- **When**: 生成Markdown报告
- **Then**: 包含Mermaid流程图（flowchart语法），展示技术演进路径和依赖关系
- **Verification**: `human-judgment`
- **Notes**: 流程图应体现从2025到2040的技术递进关系

### AC-5: 批量处理与缓存
- **Given**: 9个主题的输入数据
- **When**: 首次运行路线图生成
- **Then**: 处理所有9个主题，生成结果文件并存入缓存；第二次运行时直接读取缓存（force_rerun=False）
- **Verification**: `programmatic`

### AC-6: 整合报告生成
- **Given**: 所有主题的路线图结果
- **When**: 生成整合报告
- **Then**: 生成一份完整的Markdown报告，包含：目录/索引、每个主题的时间轴+流程图、汇总统计
- **Verification**: `human-judgment`

### AC-7: 与现有系统集成
- **Given**: 现有系统正常运行
- **When**: 启用分主题路线图模块
- **Then**: 现有三轮预测功能不受影响；分主题路线图作为附加模块可独立运行
- **Verification**: `programmatic`

### AC-8: JSON格式规范
- **Given**: 生成的路线图JSON文件
- **When**: 进行schema校验
- **Then**: JSON结构符合预定义schema，字段类型正确，无缺失必填字段
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要在分主题路线图中增加"跨主题融合节点"的标注？（当前非目标，后续可迭代）
- [ ] 时间节点是否需要更细粒度（如每3年一个节点）？（当前定为4个节点）
- [ ] 是否需要生成HTML版本的可视化报告？（当前仅Markdown+Mermaid）
- [ ] 路线图生成是否需要接入自洽性验证以提高置信度？（当前默认跟随全局配置）
