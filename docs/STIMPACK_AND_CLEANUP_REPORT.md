# Stimpack 与任务临时文件清理（2026-10-24）

目标仍为战胜用户本人。本轮从 Stimpack 建立科技选择、研究执行和战斗使用的最小链路，同时把每次任务结束时清理临时文件写入项目约定。

## 科技与执行

- 策略 `research_priority` 支持空列表或 `["stimpack"]`，仍使用 `strategy-v1`；旧空列表合法，研究选择加入策略意图比较。
- 本项目实际 SDK 枚举为 `UpgradeId.STIMPACK`。Ares `UpgradeController` / `TechUp` 推进 Barracks Tech Lab 并研究升级，pending/complete 时不重复研究。研究前保留首个 Tech Lab 的资金，可研究但钱气不足时优先攒研究费；补工人、供给和有界扩张仍在该步骤之前。
- 即使纯 Marine 编成选择 Stimpack，也会采气；LLM 快照可查看可选研究与未开始/进行中/完成状态。默认规则回退包含 Stimpack，LLM 可显式选择空列表。
- 研究完成后，Marine 与 Marauder 使用各自技能与 Buff。只在攻击/防守、附近有可见可交战威胁、生命安全且没有已有 Stim Buff 时施放。采用至少65%生命、保留技能扣血后余量及短期命令去重保护。

## PPO 和记录边界

Stim 由规则控制，不增加现有16维观测和5个 Marine PPO 动作。需要 Stim 的决策在策略采样前移出微操候选；以施法前真实上下文关闭原轨迹并标记 `stim_rule_override`，随后该单位只有一个规则技能命令，不生成假的 action/log-probability 训练行，也不把 Stim 的扣血算入此前动作的战损奖励。

Marine 指令仍走授权和仲裁；Marauder 施法后同一步跳过攻击/移动。`stim_command` 记录的是本地排队接受情况，不冒称已经得到引擎确认或产生了战斗收益。Stim 期间的实际运动/武器节奏可能改变，模型是否改善仍需后续实战观察。

## 清理范围与复用

根目录 [AGENTS.md](../AGENTS.md) 规定每任务结束清理本任务临时输出及安全缓存。工具只扫描项目自有源码目录内的 `__pycache__`、`.pytest_cache`、`.mypy_cache` 和 `.ruff_cache`，不遍历 `artifacts/`、数据、依赖环境、Git 内部或 `.local-setup`，拒绝越界路径和重解析点。

```powershell
.\tools\cleanup_workspace.ps1
.\tools\cleanup_workspace.ps1 -Apply
```

默认仅预览，`-Apply` 才清理。模型、checkpoint、回放、原始对局/训练记录、学习记忆、正式证据报告、依赖和私密配置都保留。

首次清理已删除4个缓存目录、81个缓存文件，共1,110,663字节。最终测试与私密检查后再次删除3个缓存目录中的27个文件、259,623字节；两轮合计清除108个缓存文件、1,370,286字节。最终 dry-run 在该安全白名单内为0，不包括下述受阻临时项。两个旧回放检查 JSON（共11,787字节）及一个空检查目录的删除被自动审批以 `blocked by policy` 拒绝，未提供更细原因，已停止删除并保留，不绕过该拒绝；因此不声称整个项目已经完全无临时文件。

## 验证与限制

以本地 Ares/SDK 数据核对研究来源、研究能力以及 Marine/Marauder 技能和 Buff，结合少量离线定向检查验证研究去重、资金预留、施法安全和 PPO 采样隔离。最终18项组合检查通过，覆盖 Stim 研究/施法、兵营编成、LLM+PPO 接线、策略和经济兼容；其中真实 MicroRuleBot 路径检查确认先结束旧轨迹、该帧不调用策略采样、再发唯一授权 Stim 命令。最终 diff 检查通过。本轮未启动 SC2 对局、调用 LLM API 或更新 PPO 模型，不宣称科技已在真人局验证。Stimpack 是第一项可执行研究，尚未实现通用全科技自动学习。
