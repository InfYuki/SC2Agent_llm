# 真人对手复盘与 Siege Tank / Medivac 首版

日期：2026-10-22。当前目标是战胜用户本人使用的 Terran；官方最高难度 Bot 继续作为练习基线。

## 本局实际发生了什么

原始对局：`artifacts/runs/human_20261022_163008_559257/`，正常完成，Agent `Result.Defeat`，游戏时长536.651785714秒（约8分57秒），没有错误或时间截断。`game.SC2Replay` 已保存。

`strategy_summary.json` 记录35次LLM请求、35次响应、35个合法计划，表明 LLM 确实参与指挥。`learning_report.json` 显示 LLM 跨局提示经验已更新，PPO 因有效 on-policy 样本为0而跳过；`summary.json` 的 `micro_owned_decisions=0` 与此一致。不能宣称本局完成了 PPO 梯度更新。

原 Agent 只生产 Marine，没有采气、Factory、Starport 或高级兵种生产与控制能力。LLM 原契约也仅允许 `marine_basic`，因此需要补实际执行能力，不能只在提示词中要求它使用尚不存在的兵种。

## 用户这盘的运营节奏

根据赛后全信息 tracker 提取，以下均为游戏时间；建筑是开始建造、单位是实际出现，不能混同为建成或下达命令的时间。

| 时间 | 观察到的事件 |
|---|---|
| 0:40 | 首个 Barracks 开工 |
| 0:51 | 首个 Refinery 开工 |
| 1:37 | 二基地 Command Center 开工 |
| 2:14 | Factory 开工 |
| 2:57 | Factory Tech Lab 开工 |
| 3:57 | 首个 Siege Tank 出现 |
| 4:02 | Starport 开工 |
| 6:13 | 首批两架 Medivac 出现 |

这盘表现为较早二基地、工厂坦克衔接星港医疗运输机。Tracker 统计用户峰值51名活跃工人；累计出现44 Marine、7 Siege Tank、6 Medivac、2 Marauder、2 Viking 和1 Reaper，这些是累计数量，不能当成同一时刻的军队。Agent 峰值31工人、38 Marine，累计生产119 Marine；数量差不能直接证明哪个单一因素造成失败，但说明只补 Marine 产量不足以覆盖运营和兵种能力差距。

回放 SHA256 为 `be179f6faa6ee7c9f4311bb4c8611b83fa23a0b0919f14b39c3f7251f749cdb6`。本机回放 build98370，官方解析包没有完全对应的 schema，本轮明确采用 build98310 的兼容解码，并核对玩家槽、胜负、tracker帧上界及总时长；因此不将此分析用于精细操作或 PPO 训练。回放末帧计算536.786秒，与 Agent summary536.652秒略有末帧观测差异。完整时序与样本保存在原局 `replay_analysis/`。

## 首批高级单位功能

LLM 新增可选 `marine_tank_medivac` 生产档，默认规则也采用此混编档；旧 `marine_basic` 合法计划继续可用。混编目标为 Marine 80%、Tank 12%、Medivac 8%，是 Ares 的单位数目标比例，不是供给或资源比例。新增自动气矿、Factory/Tech Lab/Starport 科技推进和首批科技/支援单位资源储备；100游戏秒前保留Marine起步，之后优先首批科技与支援预算。由 Ares 管理建造位置、工人采气、生产前置与队列，避免持续 Marine 消费挤掉首个科技单位预算。Supply、worker、gas与扩张仍在该储备前执行，采气不被储备阻断。

Tank 使用规则控制：在可见地面目标的适当距离架起，撤退、被贴脸或脱离接战后收起并推进；不反复取消变形动画。Medivac 跟随地面部队、治疗受伤生化单位，回避可见防空单位及建筑；本轮没有空投、装载救援或额外科技升级。二者使用独立命令所有权，Marine PPO 观察与动作契约不变，不将坦克或医疗运输机伪装成 Marine 训练数据。

## 单位规则与来源

按 LoTV 科技链，Factory 的前置是 Barracks，Starport 的前置是 Factory，Siege Tank 需要 Factory 附属完成的 Tech Lab，Medivac 从 Starport 生产。Tank 的架起模式用于地面区域控制；Medivac 为生化单位提供治疗，不会治疗机械坦克。

用户指定的 [LoTV Terran 单位目录](https://liquipedia.net/starcraft2/Terran_Units_%28Legacy_of_the_Void%29) 本次直接访问返回403；搜索可读取的 [Factory LoTV 条目](https://liquipedia.net/starcraft2/Factory_%28Legacy_of_the_Void%29) 与 [Siege Tank LoTV 条目](https://liquipedia.net/starcraft2/Siege_Tank_%28Legacy_of_the_Void%29) 用于交叉核对，实际建造前置和动作仍以本机 SDK/Ares 与游戏数据为准。

Blizzard 的 [Medivac 官方指南](https://news.blizzard.com/en-us/article/5740270/game-guide-terran-medivac-drops) 说明运输与生化续航用途；本次先做跟随和治疗，不做装载空投。官方 [LoTV 多人设计说明](https://news.blizzard.com/en-us/article/20241474/legacy-of-the-void-multiplayer-design-changes) 说明 Siege Tank 的区域控制定位及 Medivac 只治疗生化单位。旧版 WoL 指南中的 Siege Mode 科技研究要求不适用于此 LoTV 实现。

## 验证边界

一次组合检查 `tests.test_terran_support tests.test_strategy tests.test_llm_ppo_runtime` 最终10项通过，覆盖混编契约、真实MacroPlan储备短路、Tank架起/收起、Medivac治疗、support/Marine所有权与无Marine控制。新增检查初期的测试fixture缺Ares路径及strategy_state已修正，最终结果为通过。另 `tests.test_human_replay_study` 一项检查验证历史时序/单位数量通过真实StrategicBot play_step到达实际提交payload，并确认同局去重；没有真实API调用。

`learn_human_match.py` 现将回放学习作为独立赛后步骤，不阻断原LLM经验/PPO更新。本机已在共享memory-dir的 `replay_protocol.json` 显式保存98370→98310兼容配对，精确schema优先，仅精确schema缺失且配置匹配时使用该配对，每局保留兼容标记与身份/时长校验；未批准的其他build报告skip。本局已不带CLIoverride重新解析成功，selection为persisted_explicit_compatibility_pair，非法98370→95299配对另一次小检查被拒绝。换机配置与依赖见[首盘复盘](HUMAN_OPPONENT_FIRST_REPLAY_REPORT.md)。本局已验证profile也可按replay SHA复用。PPO零样本原因只能定位为没有取得ownership及不匹配有限支持域，旧日志缺逐Marine拒绝原因，不能归咎于交战门禁或宣称还原全部原因。

本局原始记录和回放是实际对局来源。复盘得到的全图历史信息只用于赛后学习；下一局仍须遵守实时视野。单局时间点不代表用户永远采用相同开局，也不能把参考节奏当成新一局已确认的敌情。新单位能力的离线检查不等于下一局已经战胜用户。
