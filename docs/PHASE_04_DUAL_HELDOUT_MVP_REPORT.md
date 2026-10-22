# P4 固定双BC新双敌heldout MVP

2026-10-22，来源HEAD `ce5f9e2c08fe0c97f26948ed6a45bb65d67cbcab` 加本轮显式case/实际几何与离线评估补丁。采集前冻结原82条BC、93条候选的weights/metadata/training_report及93条NPZ/metadata共8文件；本轮0训练、0优化、0 epoch选择、0模型重导出，8文件SHA前后全同。

## 唯一采集与实际场景

新增 `dual_zergling_validation`、`dual_zergling_test` 仅供显式subset选择；默认12case×2专家=24run不扩展。两独立suite各执行一次kite专家case，无retry/补局；每局预算12游戏秒/120墙秒，两局exit0且suite passed，launcher墙秒18.031/16.719，合34.750。passed表示采集契约通过，不表示战斗胜利。

| case / suite | 名义距离 / HP / seed | 实际初态 | raw → eligible |
|---|---|---|---:|
| validation / p4_dual_validation_20261022 | 6+10；敌1/.5；己1；111 | frame26；敌距3.134765625/7.134765625；己45HP；敌35/17.6025390625HP；CD1.0087890625 | 14 → 13 |
| test / p4_dual_test_20261022 | 9+10；敌1/.5；己1；121 | frame17；敌距9/10；己45HP；敌35/17.6025390625HP；CD0 | 20 → 17 |

两敌均type105，Marine有效ground range=5+.375+.375=5.75。validation实际nearest可射、weakest不可射且两目标不同，但CD未就绪，首专家动作是RETREAT(2)，不能称立即执行NEAREST；test两敌均射程外，首APPROACH(3)。初始化移动/回血/cooldown使名义与实际不同，完整隐藏引擎态未固定。两新初始obs及obs+mask彼此及与历史dual_train不同；几何分支为观察诊断，不作战力断言。

validation有10 engine_confirmed+4 hold；test有16 confirmed+2 unconfirmed+2 hold，hold/unconfirmed不是新增引擎确认。合34 raw按既有契约取30 eligible executed_action标签，排除两条末截断及test两条未确认；obs16/mask5、8loops，error/conflict0。局部scenario_result分别frame138/6.1607142857秒与frame177/7.9017857143秒low_health_safety_exit、terminated=false/truncated=true，均未全杀。外层主动leave Defeat/stop_reason不当自然战斗结论；事后SC2残留0。

## 新冻结数据与重复审计

仅两suite均passed后，按旧正式suite→旧subset→新validation→新test顺序导出一次 `artifacts/micro_datasets/p4_dual_holdout_20261022`，123=93+13+17条，train43/validation37/test43；4summary共27个来源run、15个所选kite raw来源，只有2个run为本轮新增。重复来源引用0。旧93全部六数组前缀相同，旧validation24/test26原序和内容保留；旧val/test已历史多次使用，不重新称新heldout。

以实际NPZ float32 obs、obs+mask分别做exact审计，signed zero规范化（-0/+0相同），不使用next_obs：新validation/test分别对全部旧train/validation/test，以及两新case互比，matched_left_rows和matching_pairs均0。工具qualification.independent_heldout=true仅表示此exact观察无重叠门槛通过；group不同本身不等于状态独立，近似状态和相关轨迹未排除。

历史93条自身的train–validation、train–test、validation–test，在obs与obs+mask两审计中均分别有4/1/1个matching_pairs（matched_left_rows也为4/1/1），原样保留，不删样本；因此历史split不能称严格状态独立。工具会保留重叠证据并使新heldout资格false，缺失eligible case记missing/资格false、缺类recall=null；本轮两新case样本非空并通过exact门槛。

## 两个固定模型离线结果

`tools/evaluate_frozen_micro_bc.py`仅加载采前冻结两BC，诊断新case标签一致性；不是模型实际控制战斗。每case各一个episode，13/17行为相关轨迹，不能称30个独立场景或强泛化。

| 新case | 标签数0..4 | 原82BC loss / accuracy | 93BC loss / accuracy |
|---|---|---|---|
| validation13 | [1,3,6,0,3] | .0010418938473 / 13/13 | .0008020411478 / 13/13 |
| test17 | [0,6,7,3,1] | .0055617680773 / 17/17 | .0148346740752 / 17/17 |

两模型动作30/30一致；存在类别召回均1，validation动作3/test动作0无样本，recall=null。混淆矩阵仅对应标签计数的对角项，缺类行全0。合30条覆盖五动作不等于每case覆盖五动作、训练就绪或千条验收。93候选test loss更高，准确率无增益，不能声称新增11条训练带来收益。规则专家本身未击杀全部敌人，模仿其意图不等于学会1v2、战力、胜率或泛化提高。

## 来源、核验与边界

| 工件 | SHA256 |
|---|---|
| 采前freeze | `db4d429c69b6574ddd0a2e902f3e20c827d97b826e0a5d86014edaa04a5e70c9` |
| collection_plan | `e7c66b0727c67a4ce62e795d38f6d6bea8c4cf76b14fd0d349484bf109e11958` |
| 新validation summary | `071dae8353028a5285cc34c3b9b8eb887b83b74a54469bfe74c1a7b42c503d1c` |
| 新test summary | `457e83924da247400f0be3eeef150ca5128337dd7db92ff0c9336b76fe82db18` |
| 新validation raw | `480fe01356b362e0f5bc17f73d79928f4809b6818986b479631e7bcc9112546a` |
| 新test raw | `e3fda5484648e09487196292ba296385b24bee82ea35db389e60017e6fb228f7` |
| 新123条NPZ | `8f711539428a4b58bb03715060726e34a5f8b0f0d7f8340352cf21eb598525dd` |
| 新metadata | `b7d01b7d74b21126f7e537fd8e85f64fd5338b5782e749e6823ee5dda1927828` |
| frozen_evaluation | `e9c162562016c881e59919f8e9d4efb699c0335bc9cb33c829ec0dbfeaf32051` |
| 原82BC weights（前后同） | `e36cba313c1d8e1731573595b1b975316e1522db3af8d1a4abf4f21e405c2dcf` |
| 93BC weights（前后同） | `7f100e471aa4086ddaf5ca006ea1f6e9c29bea8812d3088e1e8b2b71a8b9e16a` |

4summary/15raw实际SHA与导出来源匹配，采集源码/地图/环境冻结前后同。独立只读scope实核raw→NPZ tail obs/mask/action、旧93前缀、8文件不变、实际几何和重复审计通过；scope未另跑游戏、训练、评估或fixture。定向离线fixture初版通过后，补缺失case显式missing/null，再执行同项通过；未跑历史全suite。详见[精简JSON](validation/p4_dual_heldout_mvp.json)和 `artifacts/p4_dual_holdout_20261022` 原始证据，模型/raw/NPZ工件Git忽略、迁移另带。

默认BC仍82条、默认PPO仍curriculum256，guard/交战门禁默认不变；动作、奖励、模型权重不改，不promote。无LLM/API、PPO训练、安装或额外测试游戏；P4训练就绪、千样本及P4/P5/P6全面验收未建立。后续训练/游戏需新预算。本轮待root最终本地保存，未push。
