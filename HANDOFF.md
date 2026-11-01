# 个人知识库 1.0 交接文档

日期：2026-11-01。交付版本：1.0.0；固定Git标签：`v1.0.0`。用户UAT已明确通过，并授权锁版交付。

## 交付入口

- [交付记录与验证限制](DELIVERY.md)
- [用户验收结论](docs/acceptance/UAT-1.0-result-20261101.md)
- [本机启动、停止与使用说明](docs/USER_GUIDE.md)
- [UAT步骤与虚构样本](docs/acceptance/UAT-20261025.md)
- [第三方来源与许可证](docs/THIRD_PARTY_NOTICES.md)

代码目录：`/Users/allenqiu/Documents/ChatGPT/个人知识库`。用户指定远程仓库为 `https://github.com/AllenQIU0713-tech/PersonalKnowledgeBase`；最终推送是否成功以本次执行结果与远程分支/标签核对为准，不能以配置origin代替推送完成。

功能基线：`fb42e68b4a9993f0e6c147390a41c9b078bcdd48`。其后至1.0增加文档、版本文件、验证摘要和启动辅助脚本，并清理过期实验资料，产品`pkb/`代码未变。`VERSION`记录1.0.0，后续新功能/修复使用新版本，不移动或覆盖v1.0.0标签。

## 运行依赖与模型

服务为Python标准库实现，数据和向量存在本机SQLite，前端为原生HTML/CSS/JavaScript。精确查找不需要模型；语义查找只需要一个本地向量模型：

- 文件：`/Users/allenqiu/Library/Application Support/PersonalKnowledgeBase/models/Qwen3-Embedding-0.6B-Q8_0.gguf`
- 大小：639,150,592字节；预期SHA256：`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`
- 既有运行时：`/opt/homebrew/Cellar/llama.cpp/0.5.0/bin/llama-server`
- 参数：`--embedding --pooling last -ub 8192 -c 4096 -np 1 --host 127.0.0.1 --port 8766`

模型文件不打入源码包，也不写入Git。交接时只核对路径和文件大小，不新增下载、构建或重新计算大模型摘要；如文件被替换，应再核对身份。

原有Reranker-0.6B-Q8_0和4B-Instruct-Q4_K_M用于未合格自动问答试验，对1.0无运行依赖。按用户2026-11-01明确指令，确认文件未占用后已移入系统废纸篓，共3,136,434,304字节；清空废纸篓后才释放空间。Embedding保留，实验报告及来源摘要保留。需要复现实验时可由用户批准恢复或重新下载，不自动执行。

自动问答、证据复核、跨资料矛盾自动判断及真实DeepSeek调用均不属本次可用范围；无需配置API密钥、启动其他模型、应用校准阈值或解除门禁。未来若恢复这些功能，应作为新版本单独验收。

## 数据与日常维护

日常双击根目录`启动知识库.command`，启动器验证依赖和空闲端口后，启动唯一需要的Embedding模型和应用、打开实际本机一次性链接。Ctrl+C或关闭终端时清理本次自有子进程，不复用或结束未知服务。实现和检查边界见 [启动器维护说明](docs/LAUNCHER.md)。新增脚本使用离线替身测试，本轮没有启动正式库或追加用户双击UAT。

正式默认目录为 `~/Library/Application Support/PersonalKnowledgeBase`。启动必须确认`--data-dir`，首次打开正式旧库可能迁移和建立索引。验收通过不表示已启用或验收真实私人资料，本次收尾未访问或迁移正式资料。

UAT曾使用`/private/tmp/pkb-uat-20261025-m7pXKY`；`XXXXXX`是创建目录的模板，不能当作原库路径重启。临时目录可能被系统清理，不作为长期正式存储。若用户要保留UAT数据，应先停止该库并按README备份；本次不删除或搬移用户UAT资料，也不结束用户自行启动的服务。

关闭网页不等于停止服务。仅在对应自有终端按Ctrl+C，先停应用再停模型；不批量结束Chrome/Python/模型。备份恢复必须显式指定资料目录并停止应用；只读文件复制不能代替应用备份与恢复核对。

## 验证证据与归档

1.0登记用户整体UAT通过结论；没有逐项结果表，不补造逐项签署。77项离线检查的既有原始输出及技术摘要随本次Git提交保存：

- `docs/testing/navigation-closeout-20261024/offline-regression-final.json`
- `docs/testing/navigation-closeout-20261024/delivery-verification.json`

技术摘要保留当时`pending_user_acceptance`状态，因为它生成于用户UAT之前；最新验收状态以单独的2026-11-01用户结论为准，不改写旧证据。

按用户最新清理要求，原始完整运行目录、冻结包、旧审计/测试/设计资料及可重建编译缓存已移出项目，位于`/Users/allenqiu/.Trash/PKB-pre1.0-experiments-20261101`，详见 [清理清单](docs/CLEANUP-1.0.json)。归档附完整文件SHA256清单，包含未入Git的旧证据，不清空废纸篓即可恢复；已入Git的旧文档也可从清理前提交`d5d40b6`取回。清理未重写Git历史，旧文档仍存在于先前提交。原始`private-*`日志不推送、不装入源码包；原失败未改为通过。

本轮保留并复跑入口安全、导航观测、删除/恢复24项回归，新增启动器测试另记。测试夹具从旧包提取到`docs/testing/fixtures/`，仅更改测试夹具路径，不改受测产品。现有`.build/extract`保留，可重建module-cache已移走。模型和实验资料归档仍占磁盘，清空废纸篓后才释放空间。

本轮最终34项检查（24项回归+10项启动器替身测试）全部通过，原始输出见 [1.0回归记录](docs/testing/final-1.0-regression.json)。`bash -n`通过。真实依赖检查确认8766端口占用/不能确认空闲而拒绝启动，未停止用户模型服务；没有以此声称真实启动全链或用户双击UAT通过。首次双击前，应先在旧模型自有终端停止旧会话。

`v1.0.0`源码包只包含Git跟踪的源码和文档；不含模型、正式资料、UAT数据库或原始私有日志。交付包保存在项目`.local-data/releases/`（Git忽略），并附SHA256。可用 `git show v1.0.0:VERSION` 检查版本，使用 `git archive` 从标签重新生成源码包。

## 后续维护与调度

项目推进自动任务5已核对为PAUSED，保持停用，不恢复五小时推进。既有角色聊天不再分发任务；维护在当前对话按用户新要求执行。当前1.0范围完成验收交付，自动问答属于明确保留的后续需求，不作为隐含后台待办。

任何新缺陷记录复现步骤、版本、实际报错和影响，创建新提交/版本并复测受影响范围；不要为文档变化重复启动大模型或回放全部历史测试。回到1.0时使用独立检出或从交付包复制，不对已有未提交资料执行强制重置。
