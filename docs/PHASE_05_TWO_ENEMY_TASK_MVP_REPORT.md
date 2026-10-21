# P5 1v2训练任务接口 MVP

日期：2026-10-21。基于本地 HEAD `0f2ffcbef055f0c6cecdb5dc4b75929cfbb0004b`；本轮未训练、未切默认模型、未push。

本轮把既有场景的两个敌人参数接入训练任务、SC2MicroEnv、worker、Gym课程轮转与trainer参数恢复。新增显式课程 `configs/micro_curriculum_two_enemy_v1.json`：保留旧三项单敌任务并追加一项1Marine对2Zergling。默认仍旧课程，两个生产启动器仍使用curriculum256；320仍需显式选择。16维特征、5动作、8loops与原奖励公式未改。旧单敌任务字典不添加second字段，历史任务及课程hash兼容；第二敌参数仅count2合法。

训练任务版本为 `marine-vs-zergling-1v2-v1`；`scenario.json`及micro recorder继续使用生成器版本 `marine-vs-zergling-v6`，两者记录对象不同，不能声称所有version相同。第二敌是同种Zergling，不表示已接异种敌军、多友军或群体策略。

## 唯一真实验收

root在实现及独立scope review放行后授权唯一episode，预冻结plan SHA256 `cff7379132250081a9b6e5a8257a28ba24e93afa0d961048490355260d10807d`。新工件 `artifacts/p5_two_enemy_task_20261021`；runtime `C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s`，SC2 `C:\Program Files (x86)\StarCraft II`，base_build98370。名义Zergling距6/己满HP/敌满HP、第二敌距8/半HP、12游戏秒/seed20261021；外墙上限90秒，最多3合法步后close，无自动retry。

唯一harness exit0、16.437墙秒，episode `512d36450c3d4d0c86872596328ec2c2`、worker PID71588。动作由harness选最低索引合法动作，actor未参与。ready frame19，obs16、mask5，两敌可见；己位置[82.28125,80]、HP45。role0/role1敌距4.4267578125/6.4267578125，HP35/17.6025390625，合计52.6025390625。名义出生距6/8及半HP17.5不等于ready实际值：初始化期间敌移动且Zerg回血，当前没有严格固定隐藏引擎态或cooldown。ready cooldown8.69580078125，攻击动作受mask关闭。

| transition frame | 合法动作 | 双敌HP总和 | enemy_hp_loss | reward |
|---|---|---|---|---|
| 27 | 2 retreat | 52.7392578125 | -0.13671875 | -0.0030381944444444445 |
| 35 | 2 retreat | 52.8759765625 | -0.13671875 | -0.0030381944444444445 |
| 43 | 0 nearest | 47.06396484375 | 5.81201171875 | 0.12915581597222223 |

三步各实际8loops，均engine_confirmed、next obs16/mask5；己HP始终45，终态奖励0。逐条复算 `(all_enemy_HP_loss-own_HP_loss)/45+terminal_reward` 一致，合计0.12307942708333333；前两步负奖励来自第二敌回血，第三步已包含首敌受伤与第二敌回血。仅证明实际聚合双敌HP和奖励，不将攻击/奖励改善解释为学会1v2。两敌到close仍活，真实all_dead终局与1v2自然死亡边界本轮未测。

decision3/frame43发预算close，直接捕获原closed ACK的episode/decision/frame/unit_slot身份匹配，接收当刻summary已存在；worker exit0。summary `interrupted/training_budget_close/result=null/error=null`，scenario_result `terminated=false/truncated=true`、1.919642857游戏秒；官方Defeat/Victory只用于leave握手，不计自然战斗胜负。close没有额外transition/终态奖励。无system_failure、rollout_discard、command_conflicts及worker/SC2残留。

## 证据与边界

plan冻结80个指定文件，包括tracked Python、旧/新课程、两默认启动器、256/320 weights、三份历史共享证据和源/安装地图，前后SHA全同；旧raw没有重写。新 `hashes.json` SHA256 `9262571760a118a9c75ebf2f8480bb700e8d6992cd9a1edf172d9f3fe749abb9`，记录工件文件身份，未读取或hash latest_state快照。新JSON摘要见 [共享证据](validation/p5_two_enemy_task_mvp.json)。原始工件/模型Git忽略，换机需另带。

3条micro raw仍为旧 `split=train`，但expert=null/bc_eligible=false/reward=null；IPC/rl_rollout有上表真实奖励，两种日志不能混称。新game目录 `learning_exclusion.json` 按micro raw SHA `1f6d66fca152247ea1dd3637794703fb145a6eaecf2bad37ab6c7a8fe5ca9b97` 与rl raw SHA `0295be9b11e9fe2ab2b6329439f9aafa4f74d9d9b4b00e741080892957562760` 永久排除未来训练，不改raw标签。initial_scene_observation内expert_action只是历史诊断字段，不构成专家标签或训练资格。

真实仅SC2MicroEnv reset→3step→close；Gym轮转和trainer贯通属于定向静态/mock覆盖，不宣称已做真实多任务训练。未追加训练、LLM/API、完整Easy局、安装、失败补局、历史suite或模型默认切换；未读.env/key/live快照。旧EOF与observer失败证据保持。P5/P6全面验收、规模训练就绪、1v2学习能力及强度/胜率/收益均未建立；后续训练或独立比较需新预算。
