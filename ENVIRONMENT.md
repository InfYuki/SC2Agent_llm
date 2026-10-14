# 本机 Ares 运行环境

建立日期：2026-10-14。项目 `D:\CODE\sc2-ares-llm-rl`。

## 固定来源

- 模板：https://github.com/AresSC2/ares-sc2-bot-template ，commit `9fc76fb2fa46cd1a876a6df36a2b8f7d5031c28a`。
- Ares 子模块：`70a151a66fdd00d6c1ee44718735d0da396b902e`，版本 3.15.0。
- 模板原 `poetry.lock` 保留；其中 python-sc2 Git commit 为 `194cd34b0ac53aa387fda65c0fc3fc3ed7452697`，MapAnalyzer 为 `10133de2b39f2adf2644f081cfdd6bf41d945da5`。
- 上游入口、bot/main.py、配置及锁文件备份：`.local-setup/upstream/`。

## 安装与隔离

Conda 环境 `sc2-ares-runtime`，解释器：

```text
C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe
```

Python 3.11.17。依赖管理工具 Poetry 2.2.1 单独放在 `.local-setup/poetry-tool/`，不是游戏或训练环境。Poetry 使用显式 VIRTUAL_ENV/CONDA_PREFIX 指向上述 Conda 环境，`virtualenvs.create=false`，通过 `install --no-root` 安装模板锁定依赖；安装前验证了 `env info --path`。

安装日志 `.local-setup/poetry-install.log`；实际环境快照 `.local-setup/installed-runtime.txt`。Poetry 此次处理 127 个安装和 2 个更新，未修改旧的 llm-starcraftii 环境。遵循模板锁文件安装了其中现有的 Notebook/打包等依赖，本轮未清理上游依赖。

主要实际版本：Ares 3.15.0、burnysc2 7.1.0（上述 Git 源码）、MapAnalyzer 0.2.0（上述 Git 源码）、cython-extensions-sc2 0.18.0、NumPy 2.4.6、protobuf 7.36.2。Cython 与自带 Rust 扩展导入通过。

Windows 用户目录中存在其他 Python 3.11 包，可能污染 Conda 环境的 pip check 与导入。本地启动和验证使用 `-s` / `PYTHONNOUSERSITE=1`，不加载用户 site-packages，不卸载其他项目包。隔离后 `pip check` 通过。

Ares 源码和其 `sc2_helper` 随子模块提供；入口按官方模板惯例，将 `ares-sc2/src` 与 `ares-sc2` 加入模块查找路径。仅安装其包元数据不足以代替模板的源码启动路径。

## 游戏和启动

游戏路径：`D:\game\StarCraft II`。首轮使用 Ancient Cistern LE，Terran vs Zerg Medium、Macro 内置 AI。每局实际 build 与技能兼容结果位于该局 `compatibility-report.json`。

```bat
cd /d D:\CODE\sc2-ares-llm-rl
run_rule.cmd
run_rule.cmd --show-config
run_rule.cmd --max-game-seconds 120 --seed 42
run_rule.cmd --no-realtime --max-game-seconds 300 --seed 42
```

默认完整实时对局，无时间限制。`--no-realtime` 固定游戏步推进，用于加速本地回归；不是训练已经实现。Ares 实时模式自行跳帧，启动事件记录实际 game_step；CLI 的 game-step 用于固定步模式。

日志：`artifacts/last-run.log`；最新局目录指针：`artifacts/latest_run.json`；每局 `manifest.json / latest_state.json / events.jsonl / summary.json / game.SC2Replay`。每局记录本项目源码哈希、子模块 commit、依赖与地图哈希。

框架模板回退：

```bat
run_rule.cmd --mode template --max-game-seconds 12 --seed 42
```

该模式保留 Ares 框架更新和诊断，没有规则经济与作战，不是可用的规则 Bot。

## 验证与重跑

```bat
conda activate sc2-ares-runtime
python -s -m pip check
python -s -m unittest discover -s tests -v
python -s tools/probe.py --mode rule --no-realtime --max-game-seconds 300 --seed 42 --wall-timeout 240
```

probe 是独立测试驱动，输出单独日志，并限制自己启动的子进程树。达到 watchdog 限制属于系统超时，不是正常胜负。原生框架游戏若把 Bot 异常转换成 Defeat，项目仍会记录异常、将该局标为 crashed 并返回非零退出码。

## 已确认的兼容适配

锁定的新 SDK 仍在 GameData 中过滤静态 AbilityId，且 UnitOrder 直接查表；4135 回归可复现 KeyError。已迁入项目内 `bot/compat.py`，从引擎读取补充技能及映射，保留未知原编号，不修改 site-packages。每局 `runtime_abilities.json` 保存诊断。回归测试同时检查真实引擎数据形式和仅观测出现的未知技能。

P0/P1 不调用 API；其基线保持可独立运行。P2 另增 `run_shadow.cmd` / `run_llm.cmd`，复用锁文件已有 requests 2.32.3，未引入新 SDK、未改动锁文件或 Ares 子模块。私有配置在 `.env.local`，环境变量优先；只连接已有的 DeepSeek 官方 HTTPS 端点。仍未创建训练环境或下载学习模型。

P2 完整实时对照发现 SDK 在游戏结束瞬间查询可用技能可能抛 game-over ProtocolError。项目 `bot/lifecycle.py` 在单次 run_game 作用域内适配：刷新官方 observation，确认本方真实 result 才正常完成，缺失结果和其他协议错误继续上抛。未改 SDK 文件；三项单测覆盖此边界，原失败局保留在 P2 报告。

## 已确认的建造管理修复

固定的 Ares 3.15.0 建造管理器先判断基地位置被占用，再检查对应任务是否完成。在首次完整对局中，这使完成二矿的 SCV 被继续派向第三矿。RuleBot 通过 Hub 的自定义 manager 接口注册项目内 `bot/building_manager.py`，在原处理前清理已完成的基地任务、计数和工人角色。规则及其派生的影子/LLM模式启用；官方 Ares 子模块保持干净。回归和修复后的完整对局已确认基地峰值为2，后续批次继续检查。
