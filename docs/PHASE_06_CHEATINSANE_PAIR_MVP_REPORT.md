# P6 CheatInsane 两局作弊压力测试

2026-10-22；唯一串行E0规则与E3规则＋PPO448各1局，均自然官方Victory、exit0、有回放；442.142857/541.785714游戏秒，总launcher墙时93.578秒，0重试/补局、0训练/LLM/API。CheatInsane是本地API枚举中的最高档作弊压力测试，不称中文“专家”档，不据此推公平难度、胜率、PPO收益或泛化；正式P6验收仍未完成。

## 配置与冻结来源

显式`--difficulty CheatInsane`；Zerg、Ancient Cistern LE、seed20261020、非实时game_step8、1200游戏秒及每局600墙秒上限、最多4名Marine逐个共享actor。E3显式选择`artifacts/models/marine_ppo_two_enemy448_20261021`，weights SHA `50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3`。guard维持默认false；低HP、支持敌种/静态防御、控数、mask及唯一命令出口保留。

冻结HEAD `af7ad148e3997369c3444f41e0f56ef0dbf79777`，运行前唯一dirty改动为`run_local.py`显式choices增加CheatVision/CheatMoney/CheatInsane并在help注明作弊压力测试；默认Medium及两入口curriculum256未变。实际运行`run_local.py` SHA `3e011748b49296a0679a62cb1310cd1c22a666603b19246c5b5820b6b52395fe`，dirty diff SHA `b003ab6ba629b50550972551c2a9e563bc7bb239f0cfb1e3b2192ca15f8c4379`。不是仅用HEAD代表运行源码。

两manifest源/地图哈希相同且各自匹配freeze，dirty diff亦匹配；map/actor前后不变。base_build98370来自当局compatibility-report，完整隐藏初态未固定。运行后源码检查为空发生在文档落盘之前，不能把随后报告编辑误称运行源码漂移。精确命令与全哈希保留在`artifacts/p6_cheatinsane_pair_20261022/freeze.json`；[精简JSON](validation/p6_cheatinsane_pair_mvp.json)只保留来源SHA及核心统计。

## 唯一两次attempt

| 模式 / run ID | 终态 / 官方结果 | 游戏秒 | launcher墙秒 | telemetry墙秒 | 峰worker / Marine / base | Marine生产计数 |
|---|---|---:|---:|---:|---|---:|
| E0 `p6_cheatinsane_e0_20261022` | completed / Victory | 442.142857 | 39.656 | 27.647267 | 45 / 59 / 2 | 86 |
| E3 `p6_cheatinsane_e3_20261022` | completed / Victory | 541.785714 | 53.922 | 41.796605 | 45 / 72 / 2 | 128 |

两局stop_reason/error均null、command_conflicts=0、无时限截断，均为自然官方终局。未来若game_time_limit主动离开，即使外层Result.Defeat也必须报截断。launcher含启动/退出，telemetry只覆盖回调跨度。E3结束游戏时刻比E0晚99.642857秒；每模式n=1、固定顺序，不能排序强弱或推学习收益。

矿库存采样峰E0/E3为1120/1940、气峰均0；最后采样分别在441.428571/541.071429游戏秒，矿1120/1745、气0、工45、Marine59/68、base2，均早于官方终局。库存、已记录生产及峰值不是累计兵损，没有全军累计损失或交换比统计，不能用生产减余兵冒充损失。

## PPO实际接管与训练域边界

E3实际1306次推理=1306 owned=1306条transition，全部请求/执行mask合法、实际与metadata均8loops，无模型载入/推理fallback。命令分为721 engine_confirmed、543 hold、23 order_preserved、19 engine_unconfirmed；后三类不冒充新增引擎确认。请求动作0..4=[7,47,693,16,543]，实际执行=[2,29,693,16,566]。233 control_released与5 unit_death是局部ownership结束，不能当整局截断或全军兵损。

448课程声明只有ZERGLING exact1/2；guard=false、domain_check事件0不能写成域外0。源obs[13]×16还原12格内受支持非飞行敌数，1..8直方图=[520,416,201,129,22,13,3,2]；370/1306（28.33%）敌数>2，确定超出声明数量域，是域外下界。其余936条数量1/2因未记录敌种仍未知，距离/HP/多友军协同等泛化也未证明。

1306条原split=train只为哈希分桶，expert=null、bc_eligible=false、reward=null/not_implemented；raw SHA `bd5faea46dd87fab20eaf5c6ff7b38b2076e8750d359af932950cad7804659f1`已有永久evaluation learning_exclusion，禁止未来训练。无训练数据导出或raw改写。

## 与历史观察的关系

上一轮同名义配置VeryHard的E0/E3自然Victory用时366.428571/384.285714秒；本轮描述性地更晚结束、Marine生产计数更高，但各模式每难度仅1局，且增加了显式CLI choices，不证明普遍难度因果或PPO收益。没有从记忆推断作弊倍数或具体作弊机制。P5微操对手仍由BotAI脚本nearest-attack控制，整局Difficulty不改变其训练对手，不能宣称修复P5收益。历史Easy旧revision/不同actor同样仅供描述性参考。

两launcher日志Traceback/ERROR/CRITICAL计数均0；执行代理终态Win32_Process检查无SC2或run_local进程残留。原始freeze/evidence、两runs/回放与actor均Git忽略，迁移需另带。未新增遥测功能、依赖安装、额外游戏/测试或默认切换；本轮本地保存、未push。后续实验需另定预算。

来源freeze SHA `35a772722936a651d35270949a7f575355c74722fdac7bbd49d5dffaf630c643`；evidence SHA `0dea4b5a91ef46f144fd2e646333e14af86982c85c988a601c437ed64e06c76b`；E3 learning_exclusion SHA `a677f0f22a2411d808dc4617e19f97b9f049237972cba03cf1ab94ba11935114`。
