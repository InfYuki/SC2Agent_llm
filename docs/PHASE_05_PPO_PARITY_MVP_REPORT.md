# P5 当前448 actor离线导出一致性MVP（2026-10-21）

唯一离线验收通过：当前448 checkpoint与对应NumPy actor在1006条真实source decision记录上，未归一化logits最大绝对误差`3.814697265625e-06`、同mask概率误差`9.834766387939453e-07`，确定性动作1006/1006一致。默认真实记录门槛1000及误差阈值1e-4均达到，near-tie阈值1e-6下0条；无无效行/重复来源。观测值distinct仅877（obs+mask亦877），不能称1000个独立或唯一状态。

## 固定对象与比较口径

来源HEAD `7cf8e69170d81677ab35f7fec000bf6fb55a2d27`。checkpoint `artifacts/micro_ppo/p5_two_enemy448_20261021/model.zip` SHA `c8d9fdd27b7ace32f776e0a476d300ba22d3278b541810ba07a3d59baf4798b2`；actor `artifacts/models/marine_ppo_two_enemy448_20261021` weights SHA `50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3`。严格核checkpoint/metadata/actor来源SHA、16features/5actions和架构/版本契约，使用既有training Python离线加载，无SC2启动或PPO优化。

SB3比较`action_net`未归一化logits，不能用Categorical已归一化distribution.logits代替；两侧使用相同raw mask。SB3确定性gold是实际distribution.probs.argmax，NumPy按生产masked logits.argmax，平局由argmax首索引决定。raw obs转换float32，记录真实obs值distinct。工具冻结SHA `12fa4613a84a18279e6536cb45b33bfa455465bac91f7acf6eaee64f899136d0`，覆盖最终SB3 mode修正，前后不变；只执行以下一次，exit0，没有失败重跑或降阈值：

```powershell
C:/code/sc2-ares-training/Scripts/python.exe -s tools/verify_micro_ppo_parity.py artifacts/micro_ppo/p5_two_enemy448_20261021/model.zip artifacts/models/marine_ppo_two_enemy448_20261021 --transitions artifacts/runs/e3_fullmatch_ppo_20261019/micro_transitions.jsonl --transitions artifacts/runs/e4_fullmatch_llm_ppo_20261019/micro_transitions.jsonl --transitions artifacts/runs/e4_fullmatch_llm_ppo_20261019_snapshotfix/micro_transitions.jsonl --transitions artifacts/runs/p6_runner_e1e3e4_20261020_E3/micro_transitions.jsonl --transitions artifacts/runs/p6_runner_e1e3e4_20261020_E4/micro_transitions.jsonl --output artifacts/p5_ppo_parity_20261021/parity.json
```

## 明确真实来源

仅从三份既有E3/E4完整局报告与固定矩阵remaining-modes报告定点选取五个`artifacts/runs/<run>/micro_transitions.jsonl`；不扫训练目录、不读凭据或任意LLM配置。只计每行source `obs`/`mask`，不用next_obs或synthetic充数。源SHA+物理行号在完整parity报告逐条保存；同raw SHA重复文件只计一次，重复obs值保留为真实source记录而另报distinct。

| run | 原始状态 | 行号 | raw SHA256 |
|---|---|---:|---|
| `e3_fullmatch_ppo_20261019` | completed/Victory | 1–233 | `2fa80043f81845a40c6a4e36b3e9cd75cd681749bd038afece694a69c226668d` |
| `e4_fullmatch_llm_ppo_20261019` | crashed/unknown | 1–110 | `f57c2b27124d1cb3612802ea407fb99cfc3ef59ddc731503a08985890d6b9ceb` |
| `e4_fullmatch_llm_ppo_20261019_snapshotfix` | completed/Victory | 1–240 | `2a02f6910cece90ce35cf6347ced765415b3fe24843284085ebdba2ebe105980` |
| `p6_runner_e1e3e4_20261020_E3` | completed/Victory | 1–220 | `2052c094b5df6dfe45ae43be69dfb1385f70871aea7f6f9acaf9cea117432cea` |
| `p6_runner_e1e3e4_20261020_E4` | completed/Victory | 1–203 | `de02cc766a04e784f6f591f23996b077ba332d39504ec3371e13a159a7919012` |

233+110+240+220+203=1006，全部obs16 finite/mask5合法非空、invalid0。首次E4原局为crashed/unknown，其失败前110条合法观测只用于推理audit，不改变失败历史或计比赛胜负。五份learning_exclusion均为true且rawSHA匹配，原始raw和sidecar未改，永久不得进入未来训练；旧split=train文字不构成训练资格。

## 边界样例与保全

8条synthetic边界单列：zero/one/minus_one/alternating_extremes各配all_legal与hold_only mask；不保证物理可达、不计真实1000。全部通过，logits最大误差`1.9073486328125e-06`、概率误差`2.444721758365631e-09`、动作差异0、near-tie0。真实记录和这8条均无near-tie，不能因此声称真实覆盖了精确平局边界。

`artifacts/p5_ppo_parity_20261021/parity.json` SHA `a735b95b9508165a074438c12ca5ba0d094d393da0ed0772a0af420a4a66d19f`，保存逐行来源、失败/near-tie列表和synthetic结果；before/after SHA清单16文件完全一致，覆盖5raw、5exclusions、checkpoint、actor weights/metadata、两默认入口及工具。共享精简证据：[p5_ppo_parity_mvp.json](validation/p5_ppo_parity_mvp.json)。原始工件与模型Git忽略，迁移需另带。

本轮0游戏/0训练/0API/0安装，无默认切换、权重更新或历史suite重跑。两个默认入口仍curriculum256、敌域guard仍显式开启；只接受当前448导出一致性，不自动完成P4 BC千样本、强度/胜率/泛化、规模训练就绪或P5/P6全面验收。旧EOF/observer/首次E4失败历史保留。实现定向check与scope独立只读review由root汇总；证据代理只执行上述唯一真实离线CLI及hash/JSON核验。未commit/push，待root最终保存。
