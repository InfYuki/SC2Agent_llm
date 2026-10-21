# P6 可选PPO交战时机门禁MVP

2026-10-22；新增显式 `--ppo-engagement-gate`，默认关闭，仅用于生产 `rule_ppo` / `llm_ppo`。唯一新CheatInsane E3完整局自然官方Victory、exit0，406.428571游戏秒、40.390433 launcher墙秒，无超时/重试/补局/训练/LLM/API。相较历史无门禁E3的541.785714秒，本次观察少135.357143游戏秒；这是改变生产接管规则后的一对历史运行观察，不是模型训练收益、胜率或泛化证明，不能据此自动启用或promote模型。

## 门禁与保留边界

候选Marine冷却就绪，且当前局部支持敌人全部同时位于己方有效对地射程及敌方对地威胁射程之外时，才交回现有RuleBot宏观路径。两侧阈值均含双方radius及entry buffer 1.0；上一轮已owned者额外加exit buffer 0.5，降低边界抖动。冷却>0或几何/射程未知时保留现有微操路径。门禁只看既有局部敌人上下文，不声称远处威胁全知。

默认关闭保留旧行为；生产低HP、支持敌种/静态防御、最多4Marine、mask、命令出口和排序不变。训练scenario、动作mask、reward及448 actor均未改；敌域guard仍false。默认两入口仍curriculum256，448与新门禁均需显式参数。本轮5项相关定向测试一次通过，没有重跑历史全suite。

旧1306条owned里，`obs[2] == 0 and obs[5]*12 > 7 and not mask[0] and not mask[1]`筛到735条冷却就绪、最近敌距离>7且两种attack mask均false的决定。旧raw缺敌type/range，不能说新门禁一定拒绝这735条。旧734条敌方向与macrogoal同向，以及具体连续退却离goal约55→59，只是本次工程动机，不证明全局变慢全由PPO退却造成。

## 配置与冻结身份

唯一run `p6_engagement_gate_e3_20261022`；CheatInsane/Zerg、Ancient Cistern LE、seed20261020、非实时8loops、最多4Marine，游戏cap1200秒/墙时cap600秒、LLM cap0。显式actor为 `artifacts/models/marine_ppo_two_enemy448_20261021`，weights SHA `50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3`，与历史无门禁局相同。base_build98370；完整隐藏初态未固定。

冻结HEAD `e3b28651c69ba5ee7dd3fd8a683328d24d3fc850` 加dirty diff SHA `1a192d60b2fb8d978fc66f6ca3e827d6d862390dd8c7b683a6382f1b8efda721`；`bot/ppo_engagement.py`、`bot/micro_bot.py`、`run_local.py`及定向test四文件已冻结快照。manifest匹配全部冻结source，运行代码/地图/actor事后不变。新门禁代码与历史运行不同，不能称同一冻结源码配对。精确命令/源码全哈希保留在 `artifacts/p6_engagement_gate_20261022/freeze.json`；共享JSON只保留精简身份与统计。

## 唯一attempt与实际接管

| 观察 | 游戏秒 | launcher墙秒 | 结果 |
|---|---:|---:|---|
| 本次E3，显式新门禁 | 406.428571 | 40.390433 | completed / 自然Victory / exit0 |
| 历史E3，无新门禁 | 541.785714 | 53.922 | completed / 自然Victory / exit0 |
| 历史E0规则 | 442.142857 | 39.656 | completed / 自然Victory / exit0 |

历史两局仅作n=1参照，本轮没有重跑E0或无门禁E3。本次stop_reason/error=null、conflict=0，有回放，无SC2/run_local残留。telemetry墙时28.164622秒与launcher跨度不同；峰worker/Marine/base为45/65/2，Marine生产74，不据此计算全军损失。

实际324推理=324owned=324raw，全部请求/执行mask合法、实际与metadata均8loops，最大同时owned4，无模型fallback。请求动作0..4=[0,21,242,0,61]，执行=[0,15,240,0,69]；252 engine_confirmed、61 hold、8 order_preserved、3 engine_unconfirmed，后三类不是新增引擎确认命令。156 control_released、4 unit_death为局部ownership结束，不能算整局截断或全军损失。

## 门禁遥测的分母

候选检查共1213：ready_outside_engagement拒绝300、cooldown_active保留692、own_attack_range保留221，accepted候选913。检查发生在最多4个实际接管名额选择之前，候选检查/accepted并不等于owned或推理次数。

check事件按signature变化去重，实际633个，其中206拒绝；103个拒绝事件此前owned，均同loop释放ownership并观察到本地macro事件。macro共128个、state均attack、command_accepted均true；这只证明本地combat_commands增加/本地命令出口接受，不是引擎确认。已记录拒绝的几何阈值违规0；不把去重事件206与累计拒绝300混为一谈。

相同旧筛法在新owned raw中为19/324（5.864%；旧735/1306，56.279%），19条请求均retreat、距离7.028–7.358；对应accepted own_attack_range、owned_previous=true、buffer1.5，属于已有owner的设计hysteresis，不是漏禁。该筛法固定距离7并非新的双向有效射程几何判定；轨迹及分母已经改变，735→19只能描述所见变化，不能计算“735条确定冗余命令被修复”或因果收益。206个去重拒绝事件均无同tag/frame PPO raw overlap。

## 域外与数据用途

guard=false，敌域check事件0。新raw obs[13]×16还原局部12格受支持非飞行敌数，>2为140/324，是超出448声明ZERGLING exact1/2数量域的下界；其余数量1/2缺type记录仍unknown，不写成全部域内。门禁不是敌域守卫，也不证明多友军协同、HP/距离泛化。

324行expert=null、bc_eligible=false、reward=null；原split=train仅哈希分桶。raw SHA `77137bf3de5b0f6d14715f7b83fb64f4d9a0c3cb3d68817d1bfc1836a734994d` 已按evaluation learning_exclusion永久排除未来训练。未改写raw、未导出训练数据。低血安全、冷却中合理退却仍保留，不把所有retreat等同错误；本报告没有原因级低HP拒绝统计。P5脚本微操对手不受整局Difficulty影响，本轮是P6生产接管修正与完整局工程观察，P5/P6全面验收尚未完成。

原始freeze/dirtydiff/源码快照/evidence、run/回放/actor均Git忽略，迁移需另带。来源精简SHA见[共享JSON](validation/p6_ppo_engagement_gate_mvp.json)。本轮待root最终本地保存、未push；后续新游戏或训练需新预算。

最终freeze SHA `de4eb03773452447769e146c1bb79ea7221b88342d4f94a37487915cdc2c2022`，evidence SHA `9c69951bb5191a9fd443fad1e05a702181f115caacbe1734a9a92688e0934c97`，原始REPORT SHA `1e1bbd6fdf5ef19fd1656d0ba8ec7103f1d59c0c8f34d1a3df78ddca943eb4ee`；learning_exclusion SHA `020bbe00b3fdf2627fcbd133756d7e099a875ffd9721ffd876689ee581619ec9`。
