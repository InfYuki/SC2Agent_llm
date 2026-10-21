# P6 可选 PPO 敌域门禁 MVP 报告

日期：2026-10-21。来源HEAD `51322f8f21265c713e36926fe2af4ce392330b73` 加本轮未提交实现，精确运行代码由plan和manifest的源码SHA冻结。独立scope静态review无阻断后root授权唯一真实case；本报告writer执行该case和离线证据归并，不重跑测试。

## 2026-10-21 P6可选PPO敌域门禁MVP

新增显式 `--ppo-enemy-domain-guard`，默认false；从当前NumPy actor的producer.curriculum.tasks（缺curriculum时才取task）白名单解析敌种与exact数量对，非法/未知域整组拒绝，混种或域外回现有规则且不调用actor。门禁在eligible之前，未改动作mask、奖励或权重，也不限制/证明友军协同。已知448允许ZERGLING1/2，默认256仅1；关闭guard保留旧行为。默认两启动器仍curriculum256，guard不会自动打开，448必须显式选模型并传flag。

唯一真实双敌448 guard-on短case `p6_ppo_enemy_guard448_20261021`，test/seed20261021/名义距6+8、第二敌半HP/12游戏秒上限，无low-health绕过；exit0/17.125墙秒（90上限），无retry。12accepted=12推理=12owned=12条合法16obs/5mask/实际8loops；前9双敌后3单敌，4confirmed+7hold+1preserved（后两者非新确认命令），无error/conflict/PPO或micro异常fallback。末PPO source10HP→next5HP，frame121没有新增PPO决定，20%生产HP边界保留。局部frame121/5.4017857秒 `low_health_safety_exit`、truncated，己5HP/余1敌23.2734375HP；未击杀全部，不把外层主动leave Defeat当战斗终局。低血安全出口属于现有支持门，不是敌域拒绝；没有原因级unsupported计数。

plan SHA `65a9e78b1cd1087788757ce9755b81d9b2725f581caf97b0bbd7e8e39e14612f`；source/map/actor/default冻结哈希前后同，无SC2残留。实际初始frame25己45HP/CD.26196289，两敌距3.134765625/5.134765625、HP35/17.602539，初始化运动/回血未标准化。12条raw test/expert=null/bc_eligible=false/reward=null，并按SHA永久learning_exclusion，不当专家或训练数据。旧256双敌/unknown/混种与关闭兼容仅合并mock（同项合并mock初版及收紧后必要重跑共2次均通过，证据writer未重跑），无额外真实负例。

见[敌域门禁报告](PHASE_06_PPO_ENEMY_DOMAIN_GUARD_MVP_REPORT.md)及[共享JSON](validation/p6_ppo_enemy_domain_guard_mvp.json)，原始 `artifacts/p6_ppo_enemy_guard_20261021` 和对应runs目录Git忽略、迁移另带。仅当前metadata声明的有限敌种/数量准入工程证据，不表示已经学会；不证明友军协同、距离/HP泛化、学习收益或P5/P6全面验收；无训练/API/LLM/完整Easy/安装/默认切换/额外测试游戏/凭据或live快照读取。本轮本地提交保存，未push。

## 实现与验证边界

当前producer课程优先，不读取parent历史课程、dataset或BC祖先来扩充域。支持scenario白名单marine-vs-zergling→ZERGLING、marine-vs-marine→MARINE，数量为严格int1/2（bool/float拒绝），按原始pair匹配，不取种类×数量笛卡尔积。curriculum格式/round-robin/tasks不合法、任一task非法、未知scenario均unknown，不能退回兼容task规避。仅敌域元数据未知会在guard关闭时保留旧推理；模型加载仍走既有provenance校验。

新增一次配置事件ppo_enemy_domain_config(enabled,status,source,reason,pairs)与supported context逐帧ppo_enemy_domain_check(unit_tag,game_loop,reason,accepted,enemy_types,enemy_count)，只含白名单字段；有accepted/outside_domain/mixed_enemies/unknown_domain等计数，unsupported context不进敌域check。本例12条raw逐tag/frame全部匹配accepted check；summary PPO推理与owned计数及raw policy版本marine-ppo-numpy-v1共同证明实际PPO接管，不只是模型加载。

impl同项合并mock初版与收紧后必要重跑共2次均通过：256双敌拒绝、448双敌接受、混种拒绝、legacyunknown开guard拒绝/关闭允许；五分支合计2次infer/owned，拒绝分支无actor调用并直达issue_rule_order，不记作ppo_rule_fallback_decisions。该合并check另含partial malformed、严格数量、unsupported scenario、非法curriculum不退task与non-Cartesian pairs。mock次数/通过来源为impl release与独立scope复核，真实负例没有启动游戏。

本次无成功击杀/收益门槛，安全低血截断仍是可接受工程结果。新actorweights SHA `50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3`，source checkpoint SHA `c8d9fdd27b7ace32f776e0a476d300ba22d3278b541810ba07a3d59baf4798b2`；未修改模型或raw。初始expert_action为旧诊断字段，不构成专家标签。所有指标与证据文件SHA见共享JSON；runtime日志正常退出并有2进程cleanup，before/after SC2名称快照均空。未为实时执行中间态添加测量，也未声称主动leave等于训练worker close ACK验证。
