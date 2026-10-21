# P5 首次双敌课程PPO训练 MVP

日期：2026-10-21。基于本地 HEAD `8e9969e5918b6752a59b9e1c2e9b922e5222593a`。唯一沿320 checkpoint新增128真实步，累计448，首次实际采到27条1v2训练transition并完成导出。只证明课程训练覆盖与更新闭环，不证明学会1v2、训练收益或P5/P6全面验收。

## 唯一训练与课程变更

训练目录 `artifacts/micro_ppo/p5_two_enemy448_20261021`，parent `artifacts/micro_ppo/p5_close_resume320_20261021_observerfix`。实际训练解释器 `C:\code\sc2-ares-training\Scripts\python.exe -s`，worker使用锁定SC2 runtime。实际参数由 `p5_two_enemy448_20261021_evidence/launch.json`保存：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/p5_two_enemy448_20261021 --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --resume artifacts/micro_ppo/p5_close_resume320_20261021_observerfix --curriculum configs/micro_curriculum_two_enemy_v1.json --allow-task-change --total-timesteps 128
```

以上是已完成命令，不能直接重跑覆盖工件。本轮仅一次训练、无retry；600秒墙上限未触发，trainer174.5秒/launcher177.0004691秒、exit0。actor/critic/Adam恢复，seed42、nsteps32/batch16/epochs2/lr.0003继承，updates20→28，12项Adam step40→56；初actor与parent相同，最终finite且改变，SB3 reload概率误差0、动作相同。BC与冻结dataset来源继续透传，历史初始化报告中的optimizer空是原BC阶段记录，不是本轮Adam重新初始化。

通过 `--allow-task-change` 显式允许旧三任务→四任务；task-set规范化SHA `d9bd395a4c93492ca195c107f250863f8eee7afceedd60a8565369ff09ca53c6` → `ab7a8033fbf1624a7aa3159d3cf67443a85171e13a58296740c6b9ffcfaed49e`。新课程文件SHA `cfa3731cf6b2889bec43af436168c4aff905ccde319ba8043557d3667a61f4eb`。冷reset从index0轮转，非恢复游戏轨迹；兼容task字段仍第一项，实际由curriculum治理reset。任务1v2-v1与场景生成器v6分别记录，16features/5actions/8loops及原奖励不变。

| curriculum index | 实际任务 | 本轮样本 |
|---|---|---|
| 0 | 单Zergling距6、己满HP | 42 |
| 1 | 单Zergling距8、己满HP | 30 |
| 2 | 单Zergling距8、己.6HP | 29 |
| 3 | 双Zergling距6+8、第二敌半HP | 27 |

scope独立只读匹配128条training trace与worker raw的episode/decision/action/reward。双敌首次累计step365；两局 `24e79f371811431dbd549d8869b7847b` / `de5b0437f0c847cda678b0305651e5e3` 各13/14步，实际可见两个type105 Zergling，首条raw敌HP35+17.7392578125。两局均marine_dead；不能据混合任务回报或参数更新推1v2收益。

128条source obs16/mask5、合法mask、实际8loops；worker真实HP聚合奖励逐条复算最大误差0，trace float32奖励误差最大3.1789144e-8。系统failure/discard/conflict/expert均0。9完整训练局5enemy_dead+4marine_dead；这是训练中局部终态，不是独立胜率评估。外层旧summary的game_time_limit/truncated及官方leave Defeat/Victory不代替真实局部终态。

## 关闭、保存与导出

第128步done后SB3自动reset第10空episode `e11674f6abe249da8219c0bc468ef0d7`，0条raw，预算close summary为 `interrupted/training_budget_close/result=null/error=null`，没有额外transition/终态奖励。生产trainer的env.close成功门先于pending save→reload→最终zip；env.close强制身份匹配ACK与worker exit0，成功report/launcher exit0和末summary支撑正常关闭保存。本轮没有新增observer或独立抓原ACK时间，不声称直接测到ACK与save时间先后。10worker日志无EOF/Traceback/ERROR词，事后SC2及本run Python残留0。

新checkpoint SHA `c8d9fdd27b7ace32f776e0a476d300ba22d3278b541810ba07a3d59baf4798b2`。新NumPy actor `artifacts/models/marine_ppo_two_enemy448_20261021`，weights SHA `50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3`。唯一已有reload probe（无新环境）导出误差2.0372681319713593e-10，SB3/NumPy同action2；仅1条，非128条或千观测验收。producer保留parent/BC/dataset/curriculum/task-change来源；父320的model/metadata/weights三SHA不变，父checkpoint仍 `429b53d24e87c5b0f67bce8da7eabdb696451c37d5d9370809096606792b7b6a`。

两默认入口仍curriculum256，未promote448；新actor仅显式 `--ppo-model artifacts/models/marine_ppo_two_enemy448_20261021` 选择。后续沿新checkpoint resume可继承新课程，不重复init-BC；任何追加训练/评估仍需新预算。

## 证据与边界

精简[共享JSON](validation/p5_two_enemy_train_mvp.json)只保留关键字段与11个指定来源SHA。training_report SHA `963b20a07ca3654888a8f2506b1e82fff5af4d1d254f583de44c43ed19ec6371`，training trace SHA `a62139cf3d697fd8bc74554efcf908ec8c83f3a06ca62ecf4a513bf04f81386d`；导出/关闭证据位于同级 `p5_two_enemy448_20261021_evidence`。per-task/奖励/终态为scope独立只读核验，未额外落盘大证据树。模型/raw/evidence Git忽略，迁移另带。

没有新完整Easy局、LLM/API、额外runtime对照、默认切换、源码/配置修改、历史suite或安装；未手工读取.env/key/live快照。旧EOF与observer失败证据保留。只证明真实双敌样本参与本轮PPO课程，未建立强度/胜率/泛化/训练收益、规模就绪或P5/P6全面验收。本轮4docs由root最终保存，当前未commit/push。
