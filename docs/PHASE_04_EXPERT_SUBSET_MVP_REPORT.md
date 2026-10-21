# P4 单规则专家 subset 采集与冻结 MVP

2026-10-21，来源 HEAD `110dd79`，源码按实际 SHA 冻结。唯一显式双 Zergling / kite case 审计通过，12 条原始转移中 11 条导出到独立 NPZ；没有训练或合并旧 82 条数据集。这是原 `marine-kite-v1` 规则专家采集，不是 PPO actor 或新算法。

## 接口与执行

`tools/evaluate_micro.py` 增加可重复 `--case` / `--expert` 及 `--resume`；未选参数仍是旧 12 case × amove/kite = 24 runs。新 `dual_zergling_train` 仅显式选择，train / seed101 / 名义距离6、第二敌8且半血 / 满血Marine / 12游戏秒，每run墙钟120秒。plan冻结所选分母、完整命令、25源码SHA、解释器和实际地图SHA；pending-only恢复，不自动重试，终态失败保留，碰撞拒绝覆盖。执行锁约束同suite，不应视为所有手工启动器的全局协调。

唯一真实采集（exit0）：

```powershell
& 'C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe' -s tools/evaluate_micro.py --suite-id p4_expert_subset_20261021 --case dual_zergling_train --expert kite
```

suite scope=subset、case_count=1、run_count=1、expert=kite；没有失败重跑、换seed或放宽审计。原始run `p4_expert_subset_20261021_dual_zergling_train_kite`。`tools/export_micro_dataset.py` 继续既有eligible标签契约，新增按raw SHA校验 `learning_exclusion.json`，明确排除或无效sidecar会拒绝导出；本次真实专家raw没有排除sidecar，合法供未来训练，不能套用PPO评估数据的永久排除口径。

## 实测与标签

initial frame25，Marine type48 / 45HP / cooldown0.190185546875；Zergling type105×2，实际距离3.134765625及5.134765625、HP35及17.6025390625。初始化运动和回血使观测不同于名义配置；没有严格标准化冷却或完整隐藏引擎态。base_build98370只代表部分引擎身份。

12条均obs16、mask5、合法动作、实际8loops、expert版本`marine-kite-v1`、scenario `marine-vs-zergling-v6`、train、reward=null/not_implemented；4 engine_confirmed + 8 hold，请求/执行动作0..4均[0,2,2,0,8]，无冲突/error。hold延续已有行为，不冒充新增引擎确认命令。末frame113→121的hold因`low_health_safety_exit`截断、不eligible；其余4 confirmed + 7 hold共11条eligible。

局部frame121 / 5.401785714游戏秒低血安全退出，己5HP、余1敌，terminated=false/truncated=true，未击杀全部。外层summary的Defeat与game_time_limit仅主动leave/生命周期记录，不能替代scenario_result与末transition的局部结果。工程passed只表示采集质量审计通过，不是战斗获胜。

标签没有虚构`expert_label`字段：专家来源在versions.expert，NPZ.action逐条等于eligible原始executed_action；obs、mask、顺序逐条一致，所有标签合法。requested_action保留规则意图，不能把全raw requested==executed作为新增标签契约。

## 导出、恢复和冻结

在确认pending=0、全终态后，唯一终态恢复 `--suite-id p4_expert_subset_20261021 --resume` exit0 / 0.265秒，无Running输出、新增游戏0；全部原始文件SHA与mtime及plan SHA前后一致。随后既有导出CLI exit0：

```powershell
& 'C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe' -s tools/export_micro_dataset.py artifacts/micro_suites/p4_expert_subset_20261021/summary.json artifacts/micro_datasets/p4_expert_subset_20261021
```

NPZ为11×16 obs、11×5 mask、11个action/game_loop/group/split，单group `dual_zergling_train` 仅train11，validation/test均0；action0..4=[0,2,2,0,7]，缺0与3。metadata training_readiness=not_established、models_trained=false。旧82数据集两文件SHA/mtime不变、没有合并；25源码/地图SHA前后不变，事后无SC2_x64进程。

| 工件 | SHA256 |
|---|---|
| plan | `e7a9581ce3441d28c56f5cc9048c2d3389158053c9b8eff78634299769ba1e62` |
| raw micro | `6d178d167a695bcc7917637af7f96d9aa9436c779f5afd58244f797fc5213317` |
| 新NPZ | `f470c852696f6eb7a56f76cf0493544bd5d9a783ec3287ecd1dd0fe37b82b39a` |
| 新metadata | `c08f8af71b8a36d4ed8f507545be96076db4e6981251426dbeec0403ec91af55` |

完整来源SHA/core counts见[精简共享JSON](validation/p4_expert_subset_mvp.json)，原始冻结记录 `artifacts/micro_suites/p4_expert_subset_20261021/freeze_evidence.json`，含terminal_resume/export日志、原始文件hash+mtime及旧82前后hash。初始接口唯一合并check通过；独立review后仅删除不必要的requested==executed附加拒绝，再diff检查，无额外测试游戏。

## 边界

只有一个train小样本组，无validation/test，动作覆盖不全，不能直接推出BC结果、规模就绪、强度、胜率、泛化或学习收益，也不自动完成P4/P5/P6全面验收。两生产默认入口仍curriculum256，guard不自动开启。没有训练、LLM/API、完整Easy局、安装、默认切换、凭据/live latest_state读取或历史suite追加。原始工件Git忽略、迁移需另带；后续采集/训练/评估需新预算。本轮待root最终保存、未push。
