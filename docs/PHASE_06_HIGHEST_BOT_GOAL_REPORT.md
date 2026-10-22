# P6 最高官方 Bot 目标与默认配置

2026-10-22：项目最高目标正式确定为**战胜最高难度官方 Bot；获胜优先，胜局越短越好，败局越久越好**。后续完整局默认 `CheatInsane`。用户允许围绕结果快速迭代，不要求每项改动先建立严格统计收益证明；必要正确性检查及真实结果记录仍保留。

本轮已通过推荐默认入口真实战胜最高档虫族：`p6_highest_goal_20261022` 自然 `Result.Victory`，401.428571 游戏秒（6分41.43秒），`completed`、`stop_reason=null`、`error=null`、exit0；一次运行，无重试。**默认最高难度、可用配置与本轮最高档虫族胜出目标已达成**。这一基线不代表所有种族、地图或种子均稳定获胜。

## 使用入口与配置

```bat
cd /d C:\code\SC2Agent_llm
run_ppo.cmd
```

推荐 `run_ppo.cmd`：448 actor（`artifacts/models/marine_ppo_two_enemy448_20261021`）+交战门禁。`run_llm_ppo.cmd` 同样默认448+门禁，为需要上层LLM时的入口。参数在脚本末尾覆盖，例如 `--no-ppo-engagement-gate`、`--ppo-model <dir>`、`--difficulty VeryHard`。通用 `run_rule.cmd` 保留纯规则模式，默认对手同为最高档；通用CLI门禁默认仍off，仅PPO推荐脚本与新评估计划开启。

`run_local.py`、`run.py` 及继承其默认的正式完整局评估入口默认CheatInsane；P5脚本微操对手不受完整局难度影响。新矩阵计划默认448+门禁，门禁仅E3/E4，旧计划不改命令。LLM提示已去除过期Medium表述。

本轮通过 `run_ppo.cmd` 省略difficulty/model/gate参数验证默认值，其他实测参数为Zerg、Ancient Cistern LE、seed20261020、nonrealtime、8loops、最多4 Marine、LLM0、1200游戏秒上限。一般双击仍是实时完整局；本轮固定步便于快速验证。模型与原始工件Git忽略，换机需另带；模型缺失须按现有fallback记录识别。

## 结果与排序

完整局按可比配置分组：自然胜局优先，胜局按游戏时间升序、自然败局按时间降序；draw、cap/truncated、error和invalid不参加胜败排序。错误或截断不能算作“活得更久的败局”。以下为当前选中四局的描述性排序，actor/门禁/mode源码上下文随记录保留，不作改动因果归因：

| 顺序 | run_id | 自然结果 | 游戏秒 |
|---|---|---|---:|
| 1 | p6_highest_goal_20261022 | Victory | 401.428571 |
| 2 | p6_engagement_gate_e3_20261022 | Victory | 406.428571 |
| 3 | p6_cheatinsane_e0_20261022 | Victory | 442.142857 |
| 4 | p6_cheatinsane_e3_20261022 | Victory | 541.785714 |

本轮338推理=338 owned=338 raw，均实际8loops；266 engine_confirmed、3 engine_unconfirmed、8 order_preserved、61 hold。后三项不称新增引擎确认。非法请求/执行、命令冲突和模型fallback均0；回放存在，无自有残留进程。门禁315 outside/712 cooldown/221 ownrange是候选检查计数，不等于owned。enemy数量>2的数量域外下界140/338，guard仍false。评估raw永久learning_exclusion，不能用于专家或训练。

3项定向组合检查及独立核心scope通过，无额外游戏、训练或LLM/API调用。后续围绕最高档继续缩短胜局，并可扩其他种族/种子；职业回放参考可在后续需要时获取，本轮不要求下载。

## 来源

- 实测基底HEAD：`7f8824a8cafe618e5ea1c8cddd345b0395e4e309`；运行dirty diff SHA256：`114f38a540afec4d991d89963eb5986415044997f3ba570de0cb030311abd3b0`。manifest源码匹配，运行后runtime/地图/actor未变。
- `artifacts/p6_highest_goal_20261022/evidence.json` SHA256：`6c7e1c87f597139ee3808ae1ae9078a4b128871110774904d891b7edbc9f952f`。
- 同目录 `REPORT.md` SHA256：`b8297f2cbe795a846fb67bf0a2791af4a785afacd658b9d66cc7e6850a999b60`；`key_hashes.json` SHA256：`a6e5b515ad0c53ff3671bd9879c787328be5b6440a7fc33191637df135448cde`，mismatch0。
- 同目录 `freeze.json`、`goal_ranking.json` / `.md`；完整比赛 `artifacts/runs/p6_highest_goal_20261022`；共享精简证据 [p6_highest_bot_goal.json](validation/p6_highest_bot_goal.json)。本轮本地保存，未自动push。
