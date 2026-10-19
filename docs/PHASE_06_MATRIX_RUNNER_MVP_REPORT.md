# P6 固定配置矩阵 runner MVP

2026-10-20，仅验证默认 dry-run、显式执行、顺序批次、固定 attempt 清单与终态恢复流程。本轮恰 E0 Rule/Rule、E2 Rule/BC 各一局，无 LLM 请求、无训练，不构成正式 P6 或策略强度验收。

## 使用与冻结

在仓库根目录使用锁定 runtime：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/run_evaluation_matrix.py --modes E0 E2 --llm-max-calls 0 --batch-dir artifacts/evaluation_batches/p6_runner_e0e2_20261020
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/run_evaluation_matrix.py --resume artifacts/evaluation_batches/p6_runner_e0e2_20261020 --execute
```

首条已实际执行 exit0、`games_started=0`；第二条实际执行两局、exit0。已有目录不可重复创建；未来新批次须用新目录名。默认包含 E0–E4，但仅显式 `--execute` 启动游戏；本轮显式只选 E0/E2。LLM 总预算默认0、上限20，预分配给 E1/E4，未用预算不转移；未执行或实测任何 LLM 模式。

批次目录保存不可变 `plan.json`、完整分母 `state.json`、两局 console log 与离线 `report.json/md`。plan SHA（规范化对象）为 `6da47137d7e0f5c4952f6c8d0c6030673c529094e6204491f4488e1517496d01`。冻结项目 commit `9f896dee0b640db9bb4d2a4dfbd58ff62b32050c`、未提交 runner/test 的实际 SHA、Ares commit、解释器、源码、模型和安装地图；每次 attempt 前复核。源码身份包含未跟踪的实现文件，不能仅凭原 manifest 的空 tracked-diff SHA 推断运行时没有新代码。报告成稿和文档修改发生在两局及恢复检查之后。

固定 Ancient Cistern LE、Zerg Easy、非实时、game_step8、seed20261020、最多控4 Marine，每局1200游戏秒/600墙秒。安装地图 `C:\Program Files (x86)\StarCraft II\Maps\Ancient Cistern LE.SC2Map` SHA `13d075a466de88ba93aa3d9f3e9f3743606bffac1bf1b5e81f42b0c56d4a9c59`，两 manifest 相同；SC2 路径为 `C:\Program Files (x86)\StarCraft II`。BC 使用 `artifacts/models/marine_bc_mvp_20261018_seed42`，weights SHA `e36cba313c1d8e1731573595b1b975316e1522db3af8d1a4abf4f21e405c2dcf`。本轮未加载 PPO，既有 curriculum256 与默认入口未改。

## 真实结果

| run | 官方结果/退出 | 游戏秒 | runner 墙秒 | Marine 峰值/累计 | 冲突/error |
|---|---|---:|---:|---|---|
| `p6_runner_e0e2_20261020_E0` | Victory / 0 | 353.571429 | 37.328 | 47 / 54 | 0 / null |
| `p6_runner_e0e2_20261020_E2` | Victory / 0 | 354.285714 | 34.656 | 50 / 54 | 0 / null |

两局均自然 completed，stop_reason=null，未触发时限，保存回放，cleanup 后无 SC2 残留。两局均44工人峰、2基地峰。`summary.wall_span_seconds` 仅主循环20.817/22.047秒，不能当作含启动清理的 runner 墙秒。两原始事件流均无 `llm_*` client/request 事件；Rule/BC 模式、调用 cap0和日志共同支持本轮实际0请求，没有读取或打印私密 .env。

E2 BC248次推理=248 owned=248条实际8loops transition，涉及24 Marine tags，非法mask0、模型fallback事件0。动作0..4为 `[0,2,120,9,117]`；125 engine_confirmed、117 hold、2 order_preserved、4 engine_unconfirmed。后两类及hold不能冒充新命令确认。78条局部truncated仅代表微操释放，不是整场截断。生产安全/支持域/控数保护继续规则，无逐原因遥测，不据此推保护次数或实际敌种分布。

248行均 split=validation、expert=null、bc_eligible=false、reward=null/not_implemented；新 run 的 `learning_exclusion.json` 按 raw SHA 永久排除未来训练。未导出数据集、更新模型或运行训练，未改旧 artifact。原始文件、两 console log、回放与 batch plan/report SHA及完整原始汇总见 [共享 JSON](validation/p6_matrix_runner_mvp.json)，原始 artifacts 和模型不入 Git，迁移需另带。

## 恢复与边界

确认 `state.json` 两 attempt 均 completed 后，原样执行一次同批 `--resume ... --execute`：exit0、0.415秒，无 pending、无新增局，run ID/PID/起止时间/墙秒和原始证据保持原值；两锁清理。每个 attempt 先持久化 running 再启动子进程；失败/unknown/interrupted不自动重跑，路径碰撞不覆盖，foreign raw不计入离线报告。批次锁和全仓 runner 执行锁不协调其它手工启动器；陈旧锁必须先人工检查 owner PID，不能删除活锁。真实故障/timeout/中断恢复本轮未另外开局验证，仅有必要定向单测与源码审查。

两run共享配置/map/source一致，但原始 manifest 仍缺 game_build；冻结安装地图不等于冻结引擎build。仅一个seed、固定E0→E2顺序、每模式一局Easy，E1/E3/E4在本批均missing；不并入旧历史局，不排名、不据时间/余兵差推BC收益或胜率。离线 aggregate 的 formal_comparison_ready=false。训练 budget-close EOFError 历史问题未修；正式 P6、多地图/种子/顺序与独立训练种子比较仍未完成。

下一步可在新授权小预算内扩展缺失模式/独立seed并先补build记录；不要重跑覆盖本批或把工程Victory当成强度结论。
