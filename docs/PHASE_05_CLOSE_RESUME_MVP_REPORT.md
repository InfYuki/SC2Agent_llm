# P5 关闭修复后续训闭环有限 MVP（2026-10-21）

沿 curriculum256 checkpoint 的唯一实际续训新增64步、累计320，完成学习→预算 close ACK/worker exit0→保存→reload→NumPy导出闭环。真实训练进程 exit0、墙89.078秒，低于300秒上限。此次证明工程闭环，不证明战斗提升、P5全面验收或规模训练就绪；默认 `run_ppo.cmd`/`run_llm_ppo.cmd` 仍用 curriculum256。

## 实际执行与失败保留

首次观测 harness 在 learn 初始化 reset 的空 `bridge.close()` 读取尚不存在的 `episode_id`，AttributeError、exit1；0 worker、0真实step、未生成有效checkpoint/actor。`artifacts/micro_ppo/p5_close_resume320_20261021/failed_report.json` 及 harness 原始 stderr/events/result 保留，不将此观测器错误当成生产关闭协议失败。root授权只在 artifact harness 用安全 getattr 修复，另建 observerfix 目录；此后仅一次实际64步，无失败重训或新增评估局。

实际 trainer 命令由 `artifacts/micro_ppo/p5_close_resume320_harness_20261021/run_observerfix.py` 包装，仅观测 close/save：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py C:\code\SC2Agent_llm\artifacts\micro_ppo\p5_close_resume320_20261021_observerfix --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --resume artifacts/micro_ppo/p5_curriculum256_20261019 --total-timesteps 64
```

这是本轮已完成命令记录，不应再运行覆盖既有目录。未加 initBC、课程变更或扫参；actor/critic/Adam由父checkpoint恢复，n_steps32/batch16/epochs2、lr.0003/gamma.99/GAE.95/clip.2、seed42继承。三任务仍Zergling距6满HP→距8满HP→距8己.6HP，8loops、12秒、reward scale45；每run课程从0轮转，不恢复父引擎轨迹或完整RNG。

## 真实步数与关闭顺序

64条新增 transition 全部mask合法、实际8loops，系统失败/丢弃rollout为0。课程依次0/1/2/0/1；4完整episode为14/15/14/14步，3 enemy_dead、1 marine_dead，第5局7步后预算关闭。不能以这些训练内终局估计胜率。updates16→20、12项Adam step32→40，参数finite且actor已改变；SB3保存后reload探针概率误差0、掩码动作相同。

最后episode `466fdd9b7d44445b885e80bc1ec1e364` 在decision7/frame73退出。事件记录 close_enter `1792514109282145600`，close_return `1792514111361332500`（ACK/worker78396 exit0），之后才有 save_enter `1792514111361853700`、save_return `1792514111379550200`，目标先为 `model.pending.zip`，最终成功产物为 `model.zip`。harness没有独立抓取原始ACK包；ACK身份一致由生产close强制检查并正常返回体现。关闭约2.079秒，未追加transition或终态奖励。末局summary为interrupted/training_budget_close/result=null/error=null；scenario_result truncated=true/terminated=false。ACK内官方Defeat/Victory只是主动leave结果，不能计作自然战斗胜负。自有trainer/worker PID核验无残留；本次成功日志不抹去首次观测错误和旧EOF失败证据。

## 新产物与有限一致性

| 产物 | SHA256 |
| --- | --- |
| `artifacts/micro_ppo/p5_close_resume320_20261021_observerfix/model.zip` | `429b53d24e87c5b0f67bce8da7eabdb696451c37d5d9370809096606792b7b6a` |
| `artifacts/models/marine_ppo_close_resume320_20261021_observerfix/weights.npz` | `2b9a7355f8b2251ae4163ffb0e20e2851ca37081fbfd93e17a0b58f3c4a070cc` |
| 同目录 `metadata.json` | `d77630d8e40030b6404c2b1a86285032463d325d7e75c2d9211447e6b444cbda` |

producer保留课程/task语义、父checkpoint及原BC/dataset lineage；`bc_weights_used=true`说明历史来源，本轮是resume。嵌套BC初始化中的82样本/optimizer_state_empty属历史迁移证据，不能解释为本轮重置优化器。父zip SHA `9c94690a2cb8eaabfb5fd24c6c0984896825d6f27f87700335f9e41df3aaafd1`，旧BC/PPO actor及父checkpoint/metadata共14指定文件前后hash相同，默认curriculum256 weights SHA仍 `8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1`。

NumPy仅用本次training_report已有1条probe离线核对，概率最大误差 `2.3283064365386963e-10`、动作相同；不是64条/千条正式验收、独立测试集或收益评估。新actor未设默认；未来显式选择其目录，续训选择新checkpoint目录，不再initBC。

完整离线证据在 harness `observerfix_evidence/release_summary.json`、`events.jsonl`、`result.json`、`process_exit_check.json`、前后hash和`export_stdout.json`；共享摘要见 [p5_close_resume_mvp.json](validation/p5_close_resume_mvp.json)。模型/raw/artifacts Git忽略，迁移需另带。本轮未改源码、未运行LLM/API/完整Easy局/安装/历史全suite；未读凭据。关闭失败真实kill/超时与千样本部署验收仍未覆盖，正式P5/P6与强度收益仍未建立；后续训练/评估按新授权预算执行。本轮文档待root最终保存，未push，origin仍先推基线f2618cc，关闭修复提交0c830b2保留。
