# P6 VeryHard 两局规则 / PPO工程对照

2026-10-22；冻结源码HEAD `08129d758740bc9f0294f2f76855db38bb66afb2`，唯一串行E0规则与E3规则＋PPO448各1局，均自然官方Victory、exit0、保存回放。总launcher墙时75.921秒，0重试/补局、0训练/LLM/API。两局仍不能证明胜率、PPO收益或泛化，正式P6验收未完成。

## 本次配置与边界

显式`--difficulty VeryHard`，Zerg、Ancient Cistern LE、非实时、game_step8、seed20261020、1200游戏秒与每局600墙秒上限，最多4名Marine逐个共享actor。同一规则宏观；E3显式使用`artifacts/models/marine_ppo_two_enemy448_20261021`，weights SHA `50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3`。默认difficulty/两启动器curriculum256与guard=false均未改变；低HP、支持敌种/静态防御、控数、mask和唯一命令出口保持原实现。

两manifest的冻结source_hashes/map一致、dirty diff为空，只有mode/model/run ID配置差异；安装地图及actor哈希前后不变。双方base_build98370来自当局compatibility-report，仅部分引擎身份，完整隐藏初态未固定。freeze.json保留精确命令与全哈希；[精简JSON](validation/p6_veryhard_pair_mvp.json)提供来源路径和SHA，不嵌完整源码树。

这次提高的是P6完整局内置Computer难度。P5微操对手由BotAI脚本nearest-attack控制，独立于Easy/Hard/VeryHard；调整整局Difficulty不能宣称修复P5微操收益。历史Easy五模式为旧revision/不同actor的描述性参考，不能作为严格难度因果比较。

## 唯一两次attempt

| 模式 / run ID | 终态 / 官方结果 | 游戏秒 | launcher墙秒 | telemetry墙秒 | 峰worker / Marine / base | Marine生产计数 |
|---|---|---:|---:|---:|---|---:|
| E0 `p6_veryhard_e0_20261022` | completed / Victory | 366.428571 | 38.218 | 22.044117 | 44 / 54 / 2 | 61 |
| E3 `p6_veryhard_e3_20261022` | completed / Victory | 384.285714 | 37.703 | 25.650577 | 44 / 52 / 2 | 64 |

两局stop_reason/error均null、command_conflicts=0，均未达到时限；此为自然官方终局。若未来game_time_limit主动离开，即使外层Result.Defeat也必须报截断。launcher包含启动/退出，telemetry墙时只覆盖回调跨度，两者不可混用。E3结束游戏时刻比E0晚17.857143秒；每模式n=1、固定顺序，不据此排序强弱或证明收益。

E0/E3采样state分别343/359条，矿库存采样峰390/445、气库存峰均0；最后采样分别在366.428571/383.571429游戏秒，矿55/430、气0、工44、Marine54/52、base2。E3末采样早于官方终局，不能写成精确终态。以上是库存及已记录生产/峰值，无完整累计兵损或交换比；不能用生产减余兵或库存变化冒充战斗损失。

## PPO实际接管及训练域风险

E3实际468次推理=468 owned=468条transition，独立scope核验全部mask合法/实际8loops，无模型载入/推理fallback事件。结果为313 engine_confirmed、142 hold、9 engine_unconfirmed、4 order_preserved；后三类不冒充新增引擎确认。请求动作0..4为[2,21,283,20,142]，实际执行为[2,19,282,19,146]。局部93 control_released截断和1 unit_death终止属于微操ownership边界，整局仍自然完成。

guard本次维持默认false，配置事件声明448课程只含ZERGLING exact1/2；domain_check事件0表示未启用检查，不能写成域外0。源obs[13]×16还原12格内受支持非飞行敌数，直方图1..8=[246,52,82,75,8,3,1,1]。170/468（36.32%）敌数>2，确定超出448声明数量域，是域外下界。raw未记录敌种，其余298条数量1/2也不能确认在课程域内；距离/HP/多友军协同等泛化同样未获证明。保留生产支持门不意味着已限制在448训练域。

468行原split=train只是哈希分桶，expert=null、bc_eligible=false、reward=null/not_implemented；本轮evaluation learning_exclusion按raw SHA `df43f49d05742595180d3dde4022c24839e2b9b9c6da3f9c9818af55223709d4`永久排除未来训练。未导出训练数据或改写raw。

原始`artifacts/p6_veryhard_pair_20261022`、两runs/回放及actor均Git忽略，迁移需另带。没有新增工具功能、代码/配置修改、安装、额外游戏/测试或凭据内容输出；只落本报告、精简JSON和README/HANDOVER接续，本轮本地提交保存、未push。全局默认不切换；后续增加难度、seed或训练需另定预算。
两份launcher日志Traceback/ERROR/CRITICAL计数均0，执行代理终态Win32_Process检查SC2/Python残留均0。freeze SHA c9e1b4826a74d08f50288a1dd9938bc685f2aa09e87d2365c75b259ba7abd94a，evidence SHA919ce3bfb60675eff2062f91388728286c15a84982f3b2b737975fbee32f9b20；E3 learning_exclusion.json SHA700ff76eb5eec9341a0eb4aa0371cd89ac98e50204882e76c36d809cf8a10a9d。来源文件未改，报告后的README/HANDOVER编辑不应误称运行时源码漂移。
