# 本地个人知识库 1.0

版本 **1.0.0**，Git标签 `v1.0.0`。2026-11-01用户确认UAT通过，授权锁版交付。范围为**人工辅助本地检索**，自动问答保持关闭。

用自然语言找相关资料，按真实余弦相似度排序，再查看来源和完整原文，由你判断。每次最多20个片段、每份资料最多2个，卡片摘录最多400字；间接相关或矛盾候选也可能出现。精确查找独立提供，可按标题、原文关键词、标签、日期或完整编号找资料。

## 一键启动

在Finder中打开项目目录，双击 **`启动知识库.command`**。终端会启动现有向量模型和应用，随后自动打开默认浏览器；若显示安全入口，点击“继续打开本机知识库”。保持终端运行。

默认打开正式目录 `~/Library/Application Support/PersonalKnowledgeBase`，首次启动旧库可能迁移并建立索引。双击不是隔离测试；启动前确认这是你准备使用的资料目录。关闭网页不会停止服务，在启动终端按 **Ctrl+C** 停止本次应用和模型。

启动器只连接 `127.0.0.1`，固定应用端口8765、模型端口8766；端口占用时退出，不结束其他进程、不复用未知模型。它只停止自己启动的子进程。没有自动安装、下载、开机自启或后台常驻。

只检查依赖、不打开资料库：

```sh
./启动知识库.command --check
```

已有终端会话时先停止对应自有服务；如需手工启动或指定独立测试目录，见 [使用说明](docs/USER_GUIDE.md)。自动打开浏览器失败时，终端会显示本次启动链接；不要转发其中的凭证。

## 运行依赖

- macOS、Python 3.9以上；Python服务无第三方包依赖。
- 既有llama.cpp运行时：`/opt/homebrew/Cellar/llama.cpp/0.5.0/bin/llama-server`。
- 唯一需要的模型：`Qwen3-Embedding-0.6B-Q8_0.gguf`，存放于 `~/Library/Application Support/PersonalKnowledgeBase/models/`。
- 模型大小639,150,592字节，SHA256：`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`。启动器核对大小，不在每次启动时重算SHA；文件更换后须另行核对。

模型、运行时和私人资料不打入源码包。原Reranker与4B Instruct实验模型已按用户要求移至废纸篓；1.0不需要它们，也不需要DeepSeek密钥。来源和许可证见 [第三方记录](docs/THIRD_PARTY_NOTICES.md)。

## 收集、编辑和删除

文字、文件统一进入本机资料库；单文件最多25MiB，文字按UTF-8处理。修改内容、隐私、旧记忆状态或删除资料后，旧候选失效，等待索引就绪再查找。来源缺失的依赖不能重新进入检索，删除来源时保留必要恢复关联账本，避免重启或备份恢复使已删除来源复活。

“禁止外发”的资料仍可本地查阅。自动问答中的“未参与”是问答资格统计，不等于本地检索不可用；该数字按片段计数。问答门禁不因本地检索就绪、UAT通过或配置API密钥而自动解除。

## 本地PDF与图片提取

使用macOS PDFKit/Vision，不调用云端OCR。现有 `.build/extract` 已保留；源码包不含本机二进制。另一台机器如需该能力，由用户明确执行：

```sh
sh scripts/build-extractor.sh
```

PDF最多300页，任务180秒超时；失败可从详情重试。音视频只保留原件，不提供转录。原件、SQLite和向量均留在指定本机目录。

## 备份与恢复

先停止知识库服务，显式指定资料目录：

```sh
python3 -m pkb.backup export /absolute/path/knowledge-backup.zip --data-dir /absolute/path/data
python3 -m pkb.backup restore /absolute/path/knowledge-backup.zip --data-dir /absolute/path/data
```

ZIP未加密。恢复采用合并而非回滚，当前资料优先，隐私不会被旧备份放宽，删除记录取并集。旧记忆保留来源/状态/历史后迁移，向量按当前模型重建。恢复后应实际核对资料与删除状态。

## 验证与交接

- [交付记录](DELIVERY.md)：范围、固定功能基线、原失败与定向复测。
- [交接文档](HANDOFF.md)：数据位置、依赖、维护、清理归档和远程仓库。
- [用户验收结论](docs/acceptance/UAT-1.0-result-20261101.md)及[原UAT步骤](docs/acceptance/UAT-20261025.md)。
- [清理清单](docs/CLEANUP-1.0.json)：旧实验资料移出项目，原始证据仍可从本机归档恢复。

保留的轻量回归测试不访问正式资料、不启动模型或浏览器：

```sh
python3 -B -m unittest discover -s docs/testing/tools -p 'test_*.py' -v
```

自动问答的校准、重排和证据复核试验不是1.0使用前置。相关旧方案与试验产物已移出项目；若日后恢复该能力，需以新版本单独开发和验收。
