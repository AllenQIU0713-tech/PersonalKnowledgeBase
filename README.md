# 本地个人知识库

仅用于本机 macOS。当前按批次交付，完整范围见产品设计与交付文档。

## 启动

在项目目录运行（Python 3.9 或以上，无第三方 Python 依赖）：

```sh
python3 -m pkb.server
```

使用终端打印的一次性链接打开浏览器。地址仅绑定 `127.0.0.1:8765`，关闭进程即停止服务。新浏览器会话需要重新启动取得链接；会话不跨服务重启保留。

默认数据目录为 `~/Library/Application Support/PersonalKnowledgeBase`。原件、SQLite 数据库与后续索引均留在该目录。系统备份或用户自设同步仍可能覆盖此目录。

测试任务请固定交付提交并使用独立数据目录及端口：

```sh
python3 -m pkb.server --data-dir /private/tmp/pkb-test-B1 --port 8871
```

每文件上限 25 MiB，一次导入一份；文字目前按 UTF-8 解析。页面不加载外部字体或脚本。不要将服务映射到公网、反向代理或局域网。

本开发任务不执行测试；测试结果由「测试开发完成内容」出具，未有报告前不代表验收通过。

## 本地 PDF 与图片文字解析

先构建系统提取器（需要 Apple Command Line Tools）：

```sh
sh scripts/build-extractor.sh
```

使用系统 PDFKit/Vision，无云端 OCR。PDF 最多 300 页，每页保留页码；扫描页使用 OCR。任务单线程、180 秒超时，失败显示原因并可重试。保存完成后可重新查询或打开资料查看处理进度。音视频仅保留原件。

## 本地向量服务

安装 llama.cpp 并从 Qwen 官方下载 `Qwen3-Embedding-0.6B-GGUF` 模型属于首次联网维护操作，不会由应用自动触发。模型下载到应用支持目录或自行选择的非同步目录。当前核准文件为官方仓库修订 `370f27d7550e0def9b39c1f16d3fbaa13aa67728` 的 `Qwen3-Embedding-0.6B-Q8_0.gguf`（639,150,592 字节，SHA256 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`）。完整来源和许可证见 [第三方组件与来源记录](docs/THIRD_PARTY_NOTICES.md)。按 [Qwen 官方说明](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) 启动：

```sh
llama-server -m /absolute/path/model.gguf --embedding --pooling last -ub 8192 -c 4096 -np 1 --host 127.0.0.1 --port 8766
shasum -a 256 /absolute/path/model.gguf
python3 -m pkb.server --embedding-port 8766 --embedding-model '填入上述模型SHA256'
```

若需重新下载，使用固定修订地址：`https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/370f27d7550e0def9b39c1f16d3fbaa13aa67728/Qwen3-Embedding-0.6B-Q8_0.gguf`。下载完成后必须核对上述大小与 SHA256；不符合时不要启动。

`-c 4096 -np 1` 把向量服务限制为一个 4096 token 上下文槽，覆盖本产品单片段最多 800 字、查询最多 1000 字的输入上限。不要省略这两个参数：llama.cpp 0.5.0 的默认值会创建四个 32768 token 槽，实测内存占用约 14.0 GiB；上述单槽配置在同一模型上约 1.18 GiB。

不启用向量服务也能收集和关键词搜索。适配器禁用代理和重定向，只连接 127.0.0.1；模型标识或配置改变会重建索引。向量与分块存在本地 SQLite，查询使用余弦相似度排序与关键词排序融合。当前采用精确扫描，适合第一版小规模个人资料，不承诺大库吞吐。Qwen3-Embedding-0.6B Q8_0 已由独立测试使用 12 组中文合成样本验证：top-1 与 top-3 均为 12/12，查询中位耗时约 26.62 ms；结果不代表所有真实资料或设备。

## 个人记忆与本地备份

“我的记忆”支持手动添加、来源关联、确认、修改、失效和删除。来源资料标识可在资料详情查看。同主题不同内容标记冲突；未解决冲突、待确认、失效或禁止外发的记忆不参与回答。来源删除会删除派生记忆，清理相关已存回答及记录。

停止本地服务后执行（同目录进程锁防止边运行边恢复）：

```sh
python3 -m pkb.backup export /absolute/path/knowledge-backup.zip
python3 -m pkb.backup restore /absolute/path/knowledge-backup.zip
```

自定义目录加 `--data-dir /absolute/path/data`。备份包含原件、SQLite 一致快照和 SHA256/格式清单；上限 2 GiB，不包含服务凭证。备份是未加密 ZIP，请选择可信位置。

恢复采用合并而非回滚：现有资料优先，禁止外发设置不会被旧备份放宽；当前和备份删除记录取并集并清理派生记忆。只恢复来源仍存在且允许外发的历史回答，向量由当前模型重新建立。备份本身不会随实时删除而自动消失；在全新机器仅有旧备份时，无法得知该备份之后发生的删除，需同时携带最新备份中的删除记录。恢复后重新启动服务即可。

2026-09-25 前的缺陷版本可能丢失部分问答来源。经产品确认，升级后首次启动会一次性清空这些旧问答历史和外发记录，保留原件、索引和个人记忆，并在终端及页面显示清理数量。旧格式备份恢复时同样跳过问答历史和外发记录；升级后新导出的备份带有历史安全版本标记，可以恢复来源仍完整且允许外发的新问答。

## DeepSeek 云端回答

系统只接入 DeepSeek 官方 `https://api.deepseek.com/chat/completions`。密钥从本机环境变量读取，不写入项目、页面、普通日志、数据库或备份。可在启动服务的同一个终端中隐藏输入：

```sh
read -s DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
python3 -m pkb.server
```

本机检索完成后，先“查看并选择可用片段”，再生成发送确认页。确认页显示实际问题、空的历史消息、完整资料片段、允许使用的已确认记忆、固定指令、模型、接收地址、预期结果和完整请求 JSON。只有单独点击“确认发送给 DeepSeek”才发送一次；取消、关闭、超时、服务重启、资料内容或隐私变化均不能复用旧确认。失败不自动重试，也不切换模型。再次请求须重新生成确认页。

默认使用 `deepseek-v4-pro`；可在确认前选择 `deepseek-v4-flash`。环境变量 `DEEPSEEK_MODEL` 只在这两个允许值中选择默认项，实际模型始终在确认页显示。应用禁用系统代理与 HTTP 重定向，避免请求被静默转发；图片云端理解仍未启用，继续使用本地 OCR。

确认页提供 DeepSeek 开放平台服务条款和隐私政策入口。当前不承诺 API 零留存或一律不用于训练。外发记录只保存用途、模型、时间、来源标识、确认关联、请求摘要和结果状态，不重复保存敏感正文。
