# 首盘人类 Terran 运营复盘与策略经验

目标已改为战胜用户本人。本报告只描述一盘已完成对局，不把一次打法当作稳定习惯。

来源 `human_20261022_163008_559257`，Agent 自然败北，summary 游戏时间 **536.65 秒**。LLM 35 次请求均得到有效计划；PPO 没有取得控制权，rollout 为 0，赛后如实跳过训练。这盘没有发生 PPO 参数更新。LLM 原有赛后通用经验已保存，本轮进一步用真实 replay tracker 补充具体运营事实。

## 实际观察的运营流程

以下均为回放中 **HumanTerran 玩家 1** 的赛后全局 tracker 事实。建筑区分开工、完工；单位时间为创建完成，不把生产开始算作出兵。

| 游戏时间 | 人类操作证据 |
|---|---|
| 0:17.23 | 首 Supply Depot 开工 |
| 0:40.36 / 0:50.94 | 首 Barracks / Refinery 开工 |
| 1:36.70 → 2:48.13 | 第二 Command Center 开工 → 完工 |
| 2:13.97 → 2:56.83 | Factory 开工 → 完工 |
| 2:15.05 | 首 Reaper 创建 |
| 2:29.51 | Bunker 开工 |
| 2:57.19 → 3:15.05 | Factory Tech Lab 开工 → 完工 |
| 3:57.23 | 首 Siege Tank 创建；第二辆 4:32.99 |
| 4:02.01 → 4:37.72 | Starport 开工 → 完工 |
| 4:46.16 → 5:21.88 | Starport Reactor 开工 → 完工 |
| 6:12.72 / 6:12.90 | 首批两架 Medivac 创建 |
| 7:20.18 → 8:31.61 | 第三 Command Center 开工 → 完工 |

人类本局累计创建 44 Marine、7 Siege Tank、6 Medivac、2 Marauder、2 Viking、1 Reaper；这些是累计生产数量，**不是同一时刻的兵力**。经济统计采样峰值 51 个活跃工人、135 已用人口；约 4:03 为 31 工人，5:00 为 35 工人，7:01 为 45 工人。Agent 峰值只有31工人、38Marine，本局未具备气矿科技兵种生产。

下一局的策略经验包含这些事实与条件建议：侦察确认后准备机械化支援与气矿经济，不反复只用 Marine 冲已观察到的架起坦克；安全时继续经济增长。它们是规划假设，不是因果证明，也不要求机械照抄用户的精确时间。

## PPO 为什么没学

实际日志显示 Agent 累计生产119 Marine，1134个微操决策阶段，但 `micro_owned_decisions=0`；没有任何 `ppo_engagement_check` 事件。因此不是没造 Marine，也不能把零样本归因于交战门禁。

现微操契约只允许附近半径12、最多8个且全为支持类型的地面敌人，Tank/Reaper/Marauder和静态防御不在契约内。LLM可见快照首次记录敌军在292.68秒，为架起坦克；369.69秒以后为Marine与坦克的混合部队，与契约范围不匹配。但旧日志没有逐Marine拒绝原因，不能声称已经还原每次不接管的准确原因。回放绝不冒充 PPO on-policy 轨迹。

## 实际学习落盘与调用

完整时间线、经济采样与对手 profile 位于：

- `artifacts/runs/human_20261022_163008_559257/replay_analysis/human_build_timeline.json`
- 同目录 `opponent_profile.json`
- `artifacts/human_training/memory/strategy_memory.json` 的 `lessons` 与本局 `recent_matches[].postmatch_replay_profile`

现有 StrategicBot 会把有界经验放进真实请求的 `previous_human_match_experience`。一次无 API 离线检查已验证：真实 `play_step` 生成并提交的 payload 包含坦克数量、历史时间点和非实时视野声明；重复复盘同局不增加第二条匹配记录。此处是跨局提示经验，不是远端 LLM 权重微调。

`learn_human_match.py` 现在在正常赛后独立调用离线复盘；优先精确 build schema。本机已显式保存 `artifacts/human_training/memory/replay_protocol.json`，只批准本轮验证过的 **98370 → 98310** 兼容解析，因此相同游戏build的后续人类对局会自动复盘，无需每局手工输入覆盖参数。逐局仍核验玩家槽/姓名、结果、帧与耗时，结果显式保留 compatibility 标记和实际/解码build；不是“选择最近版本”的猜测。如果未来安装精确98370 schema会优先采用它。

其他未知build、未保存上述明确配置、依赖缺失或核验失败时，明确记录 `replay_study.status=skipped`，不阻断原来的 LLM 记忆/PPO 路径。已经有本局校验过且 replay SHA 匹配的 profile 时可重新注入。手工删除 `replay_protocol.json` 可停用兼容映射。配置与依赖均被Git忽略，换机需要带上或显式重新建立；不会静默为未知补丁套用协议。

## 解析依赖与限制

使用 Blizzard 官方 [s2protocol](https://github.com/Blizzard/s2protocol) 5.0.17.98310.0 与 mpyq 0.2.5，安装到 Git 忽略的 `.local-setup/replay-analysis/`，未改变游戏/训练环境的依赖。换机可执行：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s -m pip install --no-deps --target .local-setup/replay-analysis s2protocol==5.0.17.98310.0 mpyq==0.2.5
```

本局真实 build 为 **98370**，官方解析库未附此精确 schema；本轮 **显式指定98310兼容解析**，profile保留实际build和decoderbuild，未伪称精确匹配。已校验玩家槽/姓名、Agent胜负与summary一致、tracker帧不超header及耗时一致（header536.786秒，summary最后回调536.652秒）。这不是逐字节协议完全等价证明；后续有精确schema应重解析。

本局离线复现并写经验：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/analyze_human_replay.py --run-dir artifacts/runs/human_20261022_163008_559257 --protocol-build 98310 --memory-dir artifacts/human_training/memory
```

Replay SHA256：`be179f6faa6ee7c9f4311bb4c8611b83fa23a0b0919f14b39c3f7251f749cdb6`。未启动新的游戏或请求LLM API；本轮复盘没有产生PPO训练样本。

若换机未携带配置，操作员在接受上述已披露的兼容限制后，可显式建立同一对映射（不会为其他build授权）：

```powershell
New-Item -ItemType Directory -Force artifacts/human_training/memory | Out-Null
@{ format = 'human-replay-protocol-v1'; compatibility_overrides = @{ '98370' = 98310 } } | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 artifacts/human_training/memory/replay_protocol.json
```

已用本局真实回放验证自动读取该配置后选择 `persisted_explicit_compatibility_pair`，并检查非批准映射98370→95299会被拒绝；未开启游戏/API。
