# SuperDog Backtest v0.3 - Technical Design Documentation

**版本**: v0.3
**状态**: 设计完成，待审核
**完成日期**: 2025-12-04

---

## 📚 文档导航

### 🎯 从这里开始

**新手**: 先阅读 [v0.3_SUMMARY.md](v0.3_SUMMARY.md) 了解整体设计

**开发者**: 按以下顺序阅读各专项文档

---

## 📖 文档清单

### 1. [v0.3_SUMMARY.md](v0.3_SUMMARY.md) ⭐ **推荐首读**

**内容**: 完整的设计总结和实施路线图

- Executive Summary
- 核心问题解决方案
- 架构设计概览
- 实施路线图（3-5天）
- Definition of Done

**适合**: 所有人

---

### 2. [v0.3_architecture.md](v0.3_architecture.md)

**内容**: 整体架构设计

- 模块关系图
- 数据流图
- 新增/修改模块说明
- 与v0.2的兼容性分析
- 关键设计决策

**适合**: 架构师、Tech Lead

**页数**: ~12页

---

### 3. [v0.3_short_leverage_spec.md](v0.3_short_leverage_spec.md)

**内容**: 做空和槓桿的完整规格

- Broker API完整定义（含伪代码）
- SL/TP方向感知逻辑
- 槓桿资金计算公式
- 边界条件处理
- 向后兼容性保证

**适合**: 核心模块开发者

**页数**: ~18页

---

### 4. [v0.3_portfolio_runner_api.md](v0.3_portfolio_runner_api.md)

**内容**: Portfolio Runner API规格

- 完整的class定义（RunConfig, SingleRunResult, PortfolioResult）
- `run_portfolio()` 函数实现
- 错误处理策略
- YAML配置文件集成
- 并行执行 vs 序列执行的决策

**适合**: 批量执行模块开发者

**页数**: ~16页

---

### 5. [v0.3_text_reporter_spec.md](v0.3_text_reporter_spec.md)

**内容**: 文本报表生成器规格

- `render_single()` 输出格式（含实际示例）
- `render_portfolio()` 排行表格式
- ASCII equity curve的决策（不实现）
- 完整的伪代码实现

**适合**: 报表模块开发者

**页数**: ~14页

---

### 6. [v0.3_cli_spec.md](v0.3_cli_spec.md)

**内容**: 命令行接口规格

- 完整的命令格式和参数说明
- 参数验证规则
- 错误处理策略（含示例输出）
- CLI执行流程图
- 帮助信息完整定义

**适合**: CLI开发者

**页数**: ~15页

---

### 7. [v0.3_test_plan.md](v0.3_test_plan.md)

**内容**: 完整的测试计划

- 62个测试案例详细列表
- 测试金字塔（单元/集成/E2E）
- 测试数据和夹具
- 覆盖率目标（85%+）
- v0.2兼容性测试

**适合**: QA工程师、所有开发者

**页数**: ~20页

---

## 🎯 快速查询

### 按角色查询

| 角色 | 推荐阅读顺序 |
|------|--------------|
| **产品经理** | SUMMARY → architecture |
| **架构师** | SUMMARY → architecture → short_leverage |
| **后端开发** | SUMMARY → 对应模块文档 → test_plan |
| **QA工程师** | SUMMARY → test_plan → 所有模块文档 |
| **Tech Lead** | 全部文档 |

### 按任务查询

| 任务 | 相关文档 |
|------|----------|
| 了解整体设计 | SUMMARY, architecture |
| 实现做空功能 | short_leverage_spec |
| 实现批量回测 | portfolio_runner_api |
| 实现报表 | text_reporter_spec |
| 实现CLI | cli_spec |
| 编写测试 | test_plan |

### 按问题查询

| 问题 | 在哪个文档 |
|------|------------|
| 做空的PnL怎么计算？ | short_leverage_spec §3-4 |
| 空单的SL/TP逻辑是什么？ | short_leverage_spec §3.1 |
| 槓桿的资金模型是什么？ | short_leverage_spec §4 |
| PortfolioResult的API是什么？ | portfolio_runner_api §2.3 |
| 报表格式是什么样的？ | text_reporter_spec §3 |
| CLI的错误处理怎么做？ | cli_spec §6 |
| 有多少个测试案例？ | test_plan §2-7 |
| v0.2兼容性怎么保证？ | architecture §3, short_leverage_spec §6 |

---

## 📊 统计信息

### 文档统计

- **文档数量**: 7个
- **总页数**: ~103页
- **总字数**: ~50,000字
- **代码示例**: ~100个
- **图表**: ~15个

### 设计覆盖

- **新增模块**: 4个 (~1000行代码)
- **修改模块**: 2个 (~250行代码)
- **测试案例**: 62个
- **API定义**: 15+个class/function

### 实施估算

- **预计时间**: 3-5天
- **测试覆盖率目标**: 85%+
- **向后兼容**: 100%（v0.2所有测试通过）

---

## 🚀 实施顺序

按Phase顺序阅读和实施：

1. **Phase 1** (0.5天): [portfolio_runner_api](v0.3_portfolio_runner_api.md) §2.1 - Strategy Registry
2. **Phase 2** (1.5天): [short_leverage_spec](v0.3_short_leverage_spec.md) §2 - Broker扩展
3. **Phase 3** (0.5天): [short_leverage_spec](v0.3_short_leverage_spec.md) §3 - Engine修改
4. **Phase 4** (1天): [portfolio_runner_api](v0.3_portfolio_runner_api.md) §2-3 - Portfolio Runner
5. **Phase 5** (0.5天): [text_reporter_spec](v0.3_text_reporter_spec.md) §5 - Text Reporter
6. **Phase 6** (1天): [cli_spec](v0.3_cli_spec.md) §7 - CLI
7. **Phase 7** (0.5天): [test_plan](v0.3_test_plan.md) - 测试和文档

详见 [SUMMARY](v0.3_SUMMARY.md) §"实施路线图"

---

## ✅ 审核检查清单

在开始实施前，请确认：

### 设计审核

- [ ] 所有文档都已阅读
- [ ] 设计符合需求
- [ ] 架构合理
- [ ] API定义清晰
- [ ] 测试计划完整

### 决策确认

- [ ] 做空/槓桿的简化模型可接受
- [ ] 不实现ASCII equity curve可接受
- [ ] 序列执行（非并行）可接受
- [ ] CLI框架选择（Click/argparse）

### 资源准备

- [ ] 开发时间（3-5天）已安排
- [ ] 测试环境已准备
- [ ] 代码审核流程已明确

---

## 📞 联系和反馈

### 问题和建议

如果对设计有任何问题或建议：

1. **文档层面**: 在对应的文档中添加注释
2. **设计层面**: 更新 [DECISIONS.md](../../decisions/DECISIONS.md)
3. **实施层面**: 在实施过程中记录到 CHANGELOG

### 设计者

**Claude (Sonnet 4.5)**
- 设计日期: 2025-12-04
- 设计时长: ~4小时
- 审核状态: ⏳ 待用户审核

---

## 🎓 相关文档

### 历史版本

- [v0.1规格](../implemented/v0.1_mvp.md) - MVP回测引擎
- [v0.2规格](../implemented/v0.2_risk_upgrade.md) - Position Sizer + SL/TP

### 决策文档

- [DECISIONS.md](../../decisions/DECISIONS.md) - 所有设计决策记录
- [v0.2 Decisions](../../decisions/DECISIONS.md#v02-design-decisions) - v0.2决策
- [v0.3 Decisions](../../decisions/DECISIONS.md#v03-design-decisions) - v0.3决策

### 架构文档

- [Architecture Overview](../../architecture/overview.md) - 系统整体架构
- [Module Responsibilities](../../architecture/overview.md#2-模块职责) - 各模块职责

---

## 🎉 让我们开始构建 v0.3！

**准备好了吗？** 从 [SUMMARY](v0.3_SUMMARY.md) 开始吧！

---

**最后更新**: 2025-12-04
**文档版本**: v1.0
