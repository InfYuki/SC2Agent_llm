# P6身份追溯离线MVP

2026-10-20；基于HEAD `11996a5`，仅用既有工件补足报告工具遗漏的身份来源，无新游戏、API请求、训练或模型/依赖修改。限定下列5run均从当局 `compatibility-report.json.sc2_base_build` 追溯到98370，E1/E4从当局 `llm_config.json` 的白名单provider/model追溯到 `DeepSeek` / `deepseek-flash`。这次修正的是报告读取范围，旧manifest/raw未补写。

## 限定集合与缺项变化

| 模式 | run ID | SC2 base_build | configured provider / model | 旧工具缺项 → 新工具缺项 |
|---|---|---:|---|---|
| E0 | `p6_runner_e0e2_20261020_E0` | 98370 | 不适用 / 不适用 | game_build → 无 |
| E1 | `p6_runner_e1e3e4_20261020_E1` | 98370 | DeepSeek / deepseek-flash | game_build, llm_model → 无 |
| E2 | `p6_runner_e0e2_20261020_E2` | 98370 | 不适用 / 不适用 | game_build → 无 |
| E3 | `p6_runner_e1e3e4_20261020_E3` | 98370 | 不适用 / 不适用 | game_build → 无 |
| E4 | `p6_runner_e1e3e4_20261020_E4` | 98370 | DeepSeek / deepseek-flash | game_build, llm_model → 无 |

旧缺项直接取自未改写的 `docs/validation/p6_remaining_modes_mvp.json:fixed_five_inventory`：game_build共5项、llm_model共2项；新工具这两类缺项均为0，无身份冲突/警告。所选5run仍各1 completed/Victory，未发生新运行；这个集合不代表所有历史尝试。LLM身份状态recorded仅指配置已记录；E1/E4的requested_model及response_model仍为null，remote_behavior_frozen=false。规则模式LLM身份是not_applicable。

`comparison_groups`现能按已跟踪配置合为1组，`shared_config_complete=true`、`cross_mode_config_match=true`，共享字段无已记录差异。这是工具字段层面匹配；formal_comparison_ready与formal_strength_evidence仍为false，不能升级为正式P6或收益证据。

## 来源、冲突与保密

SC2来源链为burnysc2 `_play_game_ai` 调用 `client.ping()`，将返回的 `ping.base_build` 传给 `_prepare_start(base_build=...)`，赋入 `BotAI.base_build`，再由 `bot/probe.py` 写入本局compatibility-report。它是当局引擎ping返回的base_build，不等于完整游戏版本或data_version。

LLM仅提取本局配置provider/model有界标量；配置模型不能代替响应模型，更不能证明服务端权重/后端版本冻结。工具同时保留各候选value/source；同语义来源冲突、configured/requested不一致会记录警告并阻断配置匹配，不静默合并。缺失/非法/旧日志保持unknown或null，规则模式标为不适用。实现代理在现有1项合并定向测试中覆盖来源、冲突、legacy unknown和敏感字段排除，1/1通过；未新增测试轮次。

没有人工读取/打印.env、key、完整llm_config或base_url；报告只保存白名单身份、来源与文件SHA，不复制任意配置JSON。

## 唯一离线复现与工件完整性

仓库根目录实际执行一次（exit0）：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/report_evaluation_matrix.py p6_runner_e0e2_20261020_E0 p6_runner_e1e3e4_20261020_E1 p6_runner_e0e2_20261020_E2 p6_runner_e1e3e4_20261020_E3 p6_runner_e1e3e4_20261020_E4 --output artifacts/p6_identity_trace_20261020/evaluation_matrix.json --markdown artifacts/p6_identity_trace_20261020/evaluation_matrix.md
```

辅助矩阵位于 `artifacts/p6_identity_trace_20261020/evaluation_matrix.json` 与同名Markdown；共享摘要在[身份追溯JSON](validation/p6_identity_trace_mvp.json)。原始工件不入Git，迁移需另带；不要覆盖旧矩阵报告。本轮没有执行runner/resume/游戏启动器。

生成前后逐文件SHA比对：固定5run的33个指定证据文件全部相同，涵盖manifest、summary、events、存在的micro_transitions/learning_exclusion、compatibility-report、llm_config和回放；micro raw哈希不变。旧剩余模式报告/共享JSON、旧E4报告及原3attempt矩阵另4个历史文件SHA完全相同。共享JSON记录前后SHA及来源。

## 历史与验收边界

旧E4首次 `e4_fullmatch_llm_ppo_20261019` 仍是crashed/unknown；[原E4报告](PHASE_06_E4_FULLMATCH_MVP_REPORT.md)与[原3attempt矩阵](validation/p6_evaluation_matrix_mvp.json)保留原E4完整1/2、原3attempt完整2/3。固定5run清单独立限定，不能说所有历史5/5，也不从分母删除失败。

两个独立plan的revision仍不同，单seed/每模式n=1；完整引擎初态、完整游戏/data版本、远端模型行为、多地图/独立种子与交叉顺序均未建立。不得按时间/余兵排名或推强度、胜率、泛化和训练收益。正式P6、P5全面验收及训练budget-close EOFError历史缺口仍未完成。后续可先设计有限评估及关闭协议；任何新游戏/API预算另行授权。本轮未commit、未push，最终保存由主代理处理。
