# 兵营完整兵种生产链

日期：2026-10-24。目标：让 Agent 战胜用户本人；本轮扩大可执行兵种选择。

标准对战的兵营兵种为 Marine、Marauder、Reaper、Ghost。本轮范围为完整科技/生产入口、LLM 选择和基本队伍控制，Marine PPO 契约保持不变。

## 科技依据

精确生产前置核对固定 Ares 子模块 `ares-sc2/src/ares/dicts/unit_tech_requirement.py`、`TechUp` 和本地 python-sc2 单位生产数据。Reaper 只需 Barracks，Marauder 需要 Barracks Tech Lab，Ghost 另需 Ghost Academy；不套用旧资料中 Reaper 需要 Tech Lab 的规则，也不把核弹前置误加到普通 Ghost 生产上。

官方背景参考：[Blizzard Terran Nukes](https://news.blizzard.com/en-us/article/5838580/game-guide-terran-nukes)说明 Ghost 从 Barracks 训练并依赖 Ghost Academy，Factory 额外要求针对核弹；[Blizzard Unit Types](https://news.blizzard.com/en-us/article/4546772/game-guide-unit-types)说明 Reaper 越崖和 Ghost 施法单位分类。旧指南不作为当前伤害/费用/技能数值来源。

## 使用

继续运行 `.\run_human_training.cmd --human-fullscreen`；比赛结束仅输入 Y 才学习，N 跳过、回车/无交互待定。回放与学习批准开关保持兼容。

## 可选编成与执行

`bot/production.py` 集中定义单位数量比例，LLM 的 schema、系统提示和实时快照共享此清单。原 `strategy-v1` 结构与原有两个配置保持兼容；默认仍为 `marine_tank_medivac`，新配置由 LLM 依据可见敌情选择，不保证每一局都会造出每种兵。

| production_profile | 单位数量目标比例 |
|---|---|
| `marine_basic` | Marine 100% |
| `marine_tank_medivac` | Marine 80%、Tank 12%、Medivac 8% |
| `marine_marauder_medivac` | Marine 65%、Marauder 25%、Medivac 10% |
| `reaper_pressure` | Marine 35%、Reaper 65% |
| `ghost_support` | Marine 65%、Marauder 15%、Ghost 10%、Medivac 10% |

所有需气配置均接入既有动态采气策略，避免新步兵路线被当作纯 Marine 停采。Ares `TechUp` 按配置推进前置，`SpawnController` 核查科技和可用生产建筑；本地 Ares `get_build_structures` 使用 python-sc2 `TRAIN_INFO.requires_techlab` 并检查实际挂接的 Tech Lab，不能用地图上任意一个游离 Tech Lab 代替。

新 `FirstInfantryReserve` 在生产军队前，为首个需要的 Tech Lab、Ghost Academy、含 Medivac 配置的 Factory/Starport 和首批新单位保存矿气；不把 Tank 科技强加到 Reaper 或 Ghost 路线。补工人、供给、气矿与扩张仍在预留之前，扩张储备期间暂停低优先级科技与军队消费，保留前一轮经济修复。

新步兵取得规则作战角色，并按同一队伍战略执行 attack/move、集结与撤退；即使 Marine 全灭或 LLM 切回旧配置，已生产的新单位仍继续受控。Medivac 原有治疗逻辑适用于可治疗的生物部队，Tank/Medivac 独立控制继续保留。所有非 Marine 单位始终排除在冻结 PPO 观测与动作接口外；规则控制扩展 owner map 时不清除已发出的 Marine 命令。

## 验证

实现代理一次组合检查最终15项通过，覆盖所有配置的 schema/比例/实际宏观接线、所需科技、Reaper 无需 Tech Lab、资源不足时预留、无 Marine 时新步兵控制与撤退、Marine PPO 仲裁兼容，以及原有经济、战略、Tank/Medivac 和 LLM+PPO 组合。`git diff --check` 通过。终审核对固定 Ares 科技与 attached-TechLab 生产过滤，未再重复开局或调用 API。

本轮不包含 Stim、Concussive Shells、Reaper KD8/骚扰微操、Ghost EMP/Snipe/隐身/核弹或这些单位的 PPO 训练。Ghost 目前只做普通攻击，LLM 提示已明确这一限制，不能称为完整施法兵微操。

## 当前边界

本轮没有启动新的 SC2 对局，也没有调用 LLM API 或更新训练权重。新增兵种由规则控制，Marine PPO 继续仅处理 Marine。生产完成率与新编成的实际胜负效果留待下一场真人对练验证。
