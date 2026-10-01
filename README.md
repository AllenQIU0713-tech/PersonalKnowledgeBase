# 本地个人知识库

这是仅在本机 macOS 使用的个人资料库。所有内容从“收集”进入同一资料库；标题、原文关键词和完整编号使用独立精确查找，自然语言问题使用固定的本地 Qwen 语义索引。页面与服务只绑定 `127.0.0.1`，不会自动下载模型，也不会自动发送 DeepSeek 请求。

当前代码是 S1 语义校准候选。独立测试完成真实模型校准并由开发固化阈值前，自然语言提问会显示“等待真实模型校准”，不能用关键词结果代替。

## 启动与资料目录

需要 Python 3.9 或以上，不依赖第三方 Python 包：

```sh
python3 -m pkb.server
```

使用终端打印的一次性链接打开页面。默认数据目录为 `~/Library/Application Support/PersonalKnowledgeBase`；原件、SQLite、迁移清单和语义索引均留在本机。自定义目录和端口：

```sh
python3 -m pkb.server --data-dir /absolute/path/data --port 8871
```

每份文件最多 25 MiB，一次收集一份。文字按 UTF-8 解析。页面不加载外部字体或脚本。不要把服务映射到局域网、公网或反向代理。

测试必须固定开发通知中的提交，并使用独立检出和数据目录。本开发任务只执行静态编译、JavaScript 语法和差异检查；功能、浏览器、回归、真实模型质量和审计结论由相应独立任务出具。

## 本地 PDF 与图片文字解析

先构建系统提取器：

```sh
sh scripts/build-extractor.sh
```

提取器使用 macOS PDFKit/Vision，不调用云端 OCR。PDF 最多 300 页并保留页码；扫描页使用本地 OCR。任务单线程且有 180 秒超时，失败后可从资料详情重试。音视频只保留原件。

## 固定本地语义模型

本版本只接受官方 `Qwen3-Embedding-0.6B-Q8_0.gguf`，固定仓库修订 `370f27d7550e0def9b39c1f16d3fbaa13aa67728`，大小 639,150,592 字节，SHA256：

```text
06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439
```

来源、许可证与 llama.cpp 版本见 [第三方组件与来源记录](docs/THIRD_PARTY_NOTICES.md)。安装 llama.cpp 和下载模型属于用户明确执行的首次联网维护操作，应用不会代办。启动固定回环服务：

```sh
shasum -a 256 /absolute/path/Qwen3-Embedding-0.6B-Q8_0.gguf
llama-server -m /absolute/path/Qwen3-Embedding-0.6B-Q8_0.gguf \
  --embedding --pooling last -ub 8192 -c 4096 -np 1 \
  --host 127.0.0.1 --port 8766
python3 -m pkb.server \
  --embedding-port 8766 \
  --embedding-model 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439
```

`-c 4096 -np 1` 限制为一个上下文槽，避免 llama.cpp 默认配置造成过高内存占用。适配器禁用代理和重定向，只连接 `127.0.0.1`。模型、段落模板、查询模板或池化配置改变会创建新索引代次并清除旧校准。

页面会显示以下状态：语义服务未就绪、建立索引、索引错误、无可提问资料、等待校准、就绪。只有“就绪”允许自然语言预览、离线模拟和云端确认；任何失败都不会静默回退为关键词检索。精确查找不依赖模型，仍可按标题、原文、标签、日期和完整业务编号找回资料。

## 旧个人记忆迁移

首次启动会先为尚未迁移的旧数据创建本地 ZIP，再把每条旧个人记忆确定性地转成一份文字资料。迁移保留原主题、正文、创建/更新时间、状态、隐私、来源、冲突、修改历史和旧标识；同一旧标识重复启动不会生成重复资料。备份路径、SHA256、数量和映射写入 `migration-backups/single-library-S1-manifest.json`。

已确认、允许外发、无冲突且全部来源有效的记录才有提问资格。pending、inactive、冲突、来源缺失或解析失败会保持受限；任一来源禁止外发时，迁移资料也保持本地。旧 `memories`、`memory_sources`、`memory_history` 与 `answer_memories` 表只用于兼容恢复和旧历史清理，不参与新检索，也没有正常产品入口。

修改、删除、隐私收紧、来源变化和恢复都会让相关向量与已存回答失效。新回答只记录资料与片段标识。

## 独立校准流程

校准集 JSON 格式：

```json
{
  "passages": [{"id":"p1","title":"标题","tags":["标签"],"text":"完整片段"}],
  "queries": [{"id":"q1","text":"自然语言问题","targets":["p1"]}]
}
```

测试任务使用未参与开发调试的正例、难负例和真实固定模型测量原始余弦分数：

```sh
python3 -m pkb.calibrate measure \
  --dataset /absolute/path/calibration.json \
  --output /absolute/path/calibration-report.json \
  --data-dir /private/tmp/pkb-s1-calibration \
  --embedding-port 8766 \
  --embedding-model 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439
```

报告包含数据集 SHA256、固定模型/模板/池化签名和每个问题对全部片段的原始分数。测试依据 S1 契约选择能区分正负例的阈值，再在隔离数据目录应用：

```sh
python3 -m pkb.calibrate apply \
  --report /absolute/path/calibration-report.json \
  --threshold 0.000000 \
  --data-dir /private/tmp/pkb-s1-validation \
  --embedding-model 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439
```

这里的 `0.000000` 只是命令占位，不能作为默认值。测试须把报告哈希、候选阈值、独立验证集结果和失败样本交回开发；开发据证据固化配置并形成新的最终候选。如果不存在满足契约的阈值，保持自然语言检索不可用并反馈产品，不能加入问句特判或降低负例要求。

## 本地备份与恢复

停止服务后运行：

```sh
python3 -m pkb.backup export /absolute/path/knowledge-backup.zip
python3 -m pkb.backup restore /absolute/path/knowledge-backup.zip
```

自定义目录加 `--data-dir /absolute/path/data`。备份包含原件、SQLite 一致快照、迁移映射与 SHA256 清单，不包含服务凭证。ZIP 未加密，请存放在可信位置。

恢复采用合并而非回滚：当前资料优先，隐私不会被旧备份放宽，删除记录取并集。旧格式个人记忆先完整导入兼容表，再通过同一迁移器转成资料；归档向量不受信任，启动后按当前固定配置补建。2026-09-25 前可能缺失来源的旧问答和外发历史不会导入；新版只恢复来源完整且仍允许外发的记录。

## DeepSeek 云端回答

云端仅接入 DeepSeek 官方 `https://api.deepseek.com/chat/completions`。密钥只从启动进程的 `DEEPSEEK_API_KEY` 环境变量读取，不写入项目、页面、普通日志、数据库或备份。

本机语义检索就绪后，先查看并选择片段，再生成发送确认页。确认页展示实际问题、空历史、完整待发片段、固定指令、模型、接收地址、用途、预期结果和请求 JSON。只有单独点击“确认发送给 DeepSeek”才发送一次；取消、超时、服务重启、内容/隐私/资格变化、索引代次或校准变化都会使旧确认失效。失败不自动重试或切换模型。

默认模型为 `deepseek-v4-pro`，也可在确认前选择 `deepseek-v4-flash`。图片云端理解未启用。当前不承诺 API 零留存或一律不用于训练，确认页提供适用服务条款和隐私政策。外发记录只保存用途、模型、时间、片段标识、请求摘要和结果状态，不重复保存敏感正文。
