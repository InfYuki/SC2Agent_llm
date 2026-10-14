# P3 首轮：微操接口与真实规则专家采集

日期：2026-10-14。状态：新机恢复完成，P3首轮工程候选已实现并进行真实验收；BC/PPO尚未开始，尚未建立baseline-micro-rule-v1或学习模型。

用户补充的 `C:\Users\27932\Downloads\SC2_Ares_LLM_RL_本地开发规划.md` 已与仓库规划逐行核对，除行尾空白外一致。原文件未修改，SHA256为 `668c67305639a8f5753b504d2eaf15156f289c772d8287dc9aa7fa7789b4fefa`。本轮依据其第8节和HANDOVER推进P3，不重新开发已验收的P1/P2，不参加AI Arena。

## 实现与使用

| 交付 | 作用 | 使用 / 回退 |
|---|---|---|
| `bot/micro.py` / `MICRO_CONTRACT.md` | 16维共享特征、5动作与mask、8游戏帧节奏、规则拉扯专家 | 首轮Marine局部交战范围；修改语义须重定版本与验证 |
| `bot/micro_bot.py` | 与既有arbiter接入；规则/专家唯一owner；Ares单体及批量命令过滤；低血量/范围外/异常回退 | `run_micro.cmd`启用；`run_rule.cmd`恢复原规则路径 |
| `bot/micro_data.py` | obs/action/mask/next_obs时间对齐、引擎确认、死亡/接管边界、整局数据划分 | 每局micro_transitions.jsonl / micro_summary.json |
| `tools/report_micro.py` | 离线审计向量、mask、标签、时间、episode、整局划分与异常 | 专用运行环境执行，见下方命令 |
| `tools/run_micro_scenario.py` | 固定1v1诊断，关闭宏观，8帧推进或显式实时；局部结果独立于SC2整局离开结果 | 每进程一个场景；不是Gym环境 |

完整对局仍由Ares管理采矿、建造和生产，保留P1经济与战略选择。RuleBot仅提取原下令循环为可覆盖钩子；默认规则下令语义保持。P3使用最多4个Marine、半径12、最多8个支持的可见地面敌人。LLM/撤退任务不会交给没有任务特征的局部策略。

已按用户新增指示读取固定SmoothBrain源码的bio、common与order_utils；独立采纳干净地面网格和无效后撤条件，详见 `SMOOTHBRAIN_REFERENCE.md`。没有执行它的Bot或复制其旧依赖。当前专家严格冷却0才允许攻击，未移植cy_attack_ready前瞻，后续应作为单一候选对照。

```bat
cd /d C:\code\SC2Agent_llm
run_rule.cmd
run_micro.cmd
run_micro.cmd --no-realtime --map "Babylon LE" --seed 11
conda activate sc2-ares-runtime
python -s -m pip check
python -s -m unittest discover -s tests -v
python -s tools/run_micro_scenario.py --scenario marine-vs-zergling --seed 42
python -s tools/run_micro_scenario.py --scenario marine-vs-zergling --realtime --seed 42
python -s tools/run_micro_scenario.py --scenario marine-vs-marine --seed 42
python -s tools/report_micro.py artifacts/runs/<run_id>
```

## 新机恢复证据

- Python3.11.17 / Poetry2.2.1，原锁文件安装，pip check通过。Ares70a151a、两个Git依赖及地图哈希固定，Base98370技能兼容报告通过。
- 原25项单测通过；P3新增后40项通过，覆盖观测、mask、岩石/干净网格坐标轴、专家、订单保留、所有权与Ares批量出口、命令确认/拒绝、死亡跨决策帧和场景初始化异常。
- `restore_rule_30s`：正常启动/保存回放/退出，status=truncated，主动限时不是完整负场。
- `restore_rule_full`：完整实时Victory；游戏369.643秒/活跃wall376.697秒，比例0.98127；p95 2.171ms、最大45.125ms；0冲突，46工人/51Marine/2基地峰值。该局运行P3改动前载入的原规则代码。
- `p3_micro_realtime_42`：早期P3入口完整实时Victory；比例0.97536，p95 1.751ms，0冲突，但实际接管0次、数据0条。它只能证明入口/回退整局可用，不能证明主动实时微操。最终候选的实时主动接管另由1v1验证。

最终候选各局汇总与数据哈希见 `docs/validation/micro_v1_engineering.json`，原始日志、manifest、数据和回放仍在受忽略的artifacts目录。只有该汇总标记accepted的最终来源进入本轮候选采集清单；早期路径/出生检查候选不与其混合训练。

| 最终候选运行 | 实际结果 | 转移 / 引擎确认 / BC技术合格 | on_step p95 |
|---|---|---|---|
| p3_final_ancient_42 | Ancient Cistern LE，固定步8，完整Victory，385游戏秒 | 369 / 268 / 277 | 6.548ms |
| p3_final_babylon_11 | Babylon LE，固定步8，完整Victory，392.857游戏秒 | 226 / 173 / 159 | 5.999ms |
| p3_final_zergling_realtime | 1v1实时，敌人死亡，5.536游戏秒；SC2整局主动截断 | 15 / 10 / 13 | 见JSON，不作短场景性能外推 |
| p3_final_marine_fixed | 1v1固定步，4.688游戏秒低血量安全退出，truncated | 12 / 12 / 11 | 见JSON |

四例源码核心哈希均核对为当前实现、回放非空、0异常/0命令冲突，数据审计均通过。两场最终完整局共595条转移、441条引擎确认、436条BC技术合格；这不是训练已就绪或达到有效采集规模的声明。1v1两个结果包含成功与安全退出，不合并成“全部场景胜利”。

## 已发现问题与实测边界

首个1v1出生点靠近地图障碍，所有移动mask为False，只产生HOLD；没有把击杀结果误称专家主动控制。第二版只在地图中心搜索严格宽阔区域，找不到出生点。该版还暴露子类on_start新增异常会被SDK吞掉的问题：当时汇总误记completed/Defeat，故该局不纳入正常结果。现在全可玩区域按到中心距离搜索同高度空地，加入岩石/矿物/气矿与干净地面网格检查，并在场景on_start明确记录异常，测试覆盖保护。

固定场景局部结果独立保存：敌人死亡为局部terminated；己方≤20%血量安全退出为truncated，不伪装胜负。主动离开后的SC2整局Defeat属于限时/场景结束截断。引擎确认仅表示接受命令，不表示命中或移动已完成。

计时覆盖项目on_step钩子及相关框架更新，不是完整端到端每帧时延；短1v1的实时比例受初始化与首帧额外开销影响，不能替代完整实时比赛性能证据。完整比赛结果是少量Medium工程样本，不能证明本专家提高胜率。

## 下一阶段

1. 扩展预先冻结的1v1距离/血量/地图/种子，补齐所有动作与实际死亡/视野退出/时间上限样本；再扩固定小队。按场景/整局冻结独立验证和测试清单，当前技术合格样本数不代表训练覆盖足够。
2. 增加独立的规则A-move专家对照，比较严格冷却0与单独的攻击就绪前瞻候选，不同时改变战略/路径/奖励。
3. 完善局部有效生命损失、可见性消失、死亡和治疗统计后定义奖励。当前 `reward=null`，不可作为PPO rollout。
4. 数据与场景验收后再建独立训练环境做BC；Gym真实reset/step/IPC与PPO属于P5。本轮没有安装训练栈、训练模型或恢复任何checkpoint。
5. 新机DeepSeek密钥未配置，LLM真实API恢复与正式P2强度比较尚待进行；规则/P3持续可用。
