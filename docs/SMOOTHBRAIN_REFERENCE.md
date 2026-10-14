# SmoothBrain 参考实现记录

2026-10-14。用户指定 https://aiarena.net/bots/579/，随后提供源码 https://github.com/Myrmecoman/sc2_bot 和两个本机压缩包。本项目目标仍是本地研究和完整对局，不参加比赛。

## 已读取的来源

- GitHub 源码快照：`895d8b036af0554e8d49cc6be5925abe54da6ba2`；本机保存在忽略目录 `.local-setup/references/sc2_bot/`。
- 当前 README、`bot/bot.py`、`build_order.py`、`macro.py`、`production.py` 与 `army/manager.py` 中的相关段落；不是对其全部行为和效果的全面验证。
- 源码采用 MIT，许可副本见 `docs/licenses/SmoothBrain-LICENSE.txt`。后续若复制或改编实质代码，保留对应版权和来源。
- 作者 README 中对作弊难度 AI 的胜率描述属于作者陈述，本项目没有复现实验，不作为已验证效果。

本轮读到的当前源码使用 Ares 3.13.1 的随仓库版本及自带 python-sc2；宏观经济使用自行管理工人的逻辑，军队使用 Ares 角色、编组、影响力、路径与行为。本项目使用官方模板固定的 Ares 3.15.0，不能把它的 vendored `sc2/ares/map_analyzer` 覆盖到运行环境，也不能同时让其自管工人逻辑与 Ares Mining 管理同一批 SCV。

## 用户压缩包检查

文件保留在用户放置的旧项目根目录，没有移动或执行包内程序：

| 文件 | 大小 | 检查 |
| --- | ---: | --- |
| `D:\CODE\Large-Language-Models-play-StarCraftII\SmoothBrain.zip` | 8,121,509 bytes | 297 条目、解压总量 28,667,862 bytes，CRC 检查通过 |
| `D:\CODE\Large-Language-Models-play-StarCraftII\SmoothBrain_data.zip` | 22 bytes | 合法空 ZIP，0 条目，并非 CRC 损坏 |

Bot ZIP SHA256：`94a94b7c8dcabed70ad99f5e39dedb46f5d4c68b6e16e350fce4e67d21ab3561`。Data ZIP SHA256：`8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85`。

对 ZIP 中可比对的 bot Python 文件，36 个与上述 GitHub commit 一致，11 个不同，包括 `build_order.py`、`production.py`、`custom_utils.py` 及部分军队模块。因此两个来源不是完全相同版本，当前研究依据以明确记录的源码 commit 为主。详细比较在 `.local-setup/reference-archives.json`。

## 本阶段如何参考

| 参考点 | 本项目处理 | 状态 |
| --- | --- | --- |
| `production.py:priority_reserve`：连续购买低价兵可能让高优先级项目一直等钱 | 独立实现有超时、重试及防守释放的二矿资源预留，仍由 Ares ExpansionController 建造 | 已添加候选，真实游戏验收另见阶段报告 |
| `build_order.py`：开局受阻应有退出与恢复路径 | 避免无限阻塞后续宏观；资源预留上限 30 游戏秒 | 已纳入首版与测试 |
| `army/manager.py`：角色分离与明确姿态 | Marine 单一规则控制源；发展/集结/防守/进攻/回撤状态 | 首版已实现；复杂分队未移植 |
| `army/defense.py` 等防守编组 | 后续评估局部防守与主力任务分离，避免整军回家 | 待读取和单独实验 |
| 侦察、兵种顾问与 `reactions.py` | 后续作为规则战略和 LLM 允许选项的参考 | 未接入 |
| 各兵种专用微操与战斗模拟 | Marine 规则/RL 基线建立后逐项评估 | 未接入 |

当前没有将 SmoothBrain 整套代码作为新 Bot 执行，没有运行用户 ZIP，也没有把其战斗表现当成本项目表现。先完成最小规则底座，后续每次只引入可解释、可验证的一项行为。

补充读取 `army/orders.py`、`army/progress.py` 和 `bot/ares_compat.py`：其战术订单对象、卡住检测可作为后续战术层参考，尚未移植。它的兼容桥主要解决自带 mainline python-sc2 与 Ares 所需 fork 的差异；本项目已经采用模板锁定的 august-k/python-sc2，因此不照搬这套桥接和全局属性修改。当前需要的本机技能表适配是另外经过回归复现的问题。
