# 本地个人知识库

这是仅在本机 macOS 使用的个人资料库。所有内容从“收集”进入同一资料库；标题、原文关键词和完整编号使用独立精确查找，自然语言问题使用固定的本地 Qwen 语义索引。页面与服务只绑定 `127.0.0.1`，不会自动下载模型，也不会自动发送 DeepSeek 请求。

当前收尾交付路线是**人工辅助本地语义查找**：相关候选按真实余弦排序，展示来源、状态、版本与原文，由用户比较判断，不自动声称已得到答案。每次最多20片段、每份资料最多2片段，卡片摘录最多400字，点击查看完整原文。

自动“基于资料提问”仍保持 `calibration_required`/blocked，不能用单一余弦门槛替代答案核实；这不阻止人工语义查找。Q6或第二复核模型不作为人工查找的启用前置。下文校准和S2章节是独立自动问答试验说明，不是本次人工检索的安装/使用步骤，不应为此另行下载、构建或解除门禁。

当前交付候选、实际验证范围和待验收事项见 [交付记录](DELIVERY.md)，本机现有模型的启动步骤见 [使用说明](docs/development/assisted-retrieval-handoff-20261019/delivery-guide-draft.md)。

## 启动与资料目录

需要 Python 3.9 或以上，不依赖第三方 Python 包：

```sh
python3 -m pkb.server
```

使用终端打印的一次性链接打开页面；若显示“本机知识库安全入口”，点击一次“继续打开本机知识库”。首次跨站请求仍为403，页面里的同源链接继续使用原凭证/会话校验，不需要反复按回车或更改安全设置。进入主页后不要重复打开一次性链接。

默认数据目录为 `~/Library/Application Support/PersonalKnowledgeBase`；原件、SQLite、迁移清单和语义索引均留在本机。启动正式目录可能进行旧资料迁移和建索引，不能当作隔离测试命令。自定义目录和端口：

```sh
python3 -m pkb.server --data-dir /absolute/path/data --port 8871
```

每份文件最多 25 MiB，一次收集一份。文字按 UTF-8 解析。页面不加载外部字体或脚本。不要把服务映射到局域网、公网或反向代理。

测试须固定产品提交、工具摘要和临时合成库，不访问正式资料。历史独立审查记录保留；按用户最新要求，当前收尾实施、真实浏览器验证和结果汇总统一在当前对话完成，实施者自检不冒称新的独立审计。未完成的测试和用户验收不得写成通过。

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

本地语义查找单独显示服务未就绪、建立索引、索引错误、无资料或已就绪；只需其自身已就绪即可比较本地候选。问答状态另行显示，等待校准/缺少合格证据复核器时，回答预览、模拟和云端确认仍禁用。任何失败都不会静默把关键词结果冒充语义结果。精确查找不依赖模型，仍可按标题、原文、标签、日期和完整业务编号找回资料。

## 旧个人记忆迁移

首次启动会先为尚未迁移的旧数据创建本地 ZIP，再把每条旧个人记忆确定性地转成一份文字资料。迁移保留原主题、正文、创建/更新时间、状态、隐私、来源、冲突、修改历史和旧标识；同一旧标识重复启动不会生成重复资料。备份路径、SHA256、数量和映射写入 `migration-backups/single-library-S1-manifest.json`。

已确认、允许外发、无冲突且全部来源有效的记录才有提问资格。pending、inactive、冲突、来源缺失或解析失败会保持受限；任一来源禁止外发时，迁移资料也保持本地。旧 `memories`、`memory_sources`、`memory_history` 与 `answer_memories` 表只用于兼容恢复和旧历史清理，不参与新检索，也没有正常产品入口。

修改、删除、隐私收紧、来源变化和恢复都会让相关向量与已存回答失效。新回答只记录资料与片段标识。

删除仍被旧记忆引用的来源时，会在同一事务中将旧外键关联保留到既有 `legacy_restore_sources` 账本，再解除活引用并删除来源；旧记忆正文、历史和迁移快照保留。来源缺失的依赖不能重新进入检索，备份恢复不应使已删除来源复活。

## 独立校准流程（自动问答试验，不是人工查找前置）

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

这里的 `0.000000` 只是命令占位，不能作为默认值。如果不存在满足契约的阈值，自动问答继续关闭，不能加入问句特判或降低负例要求；人工语义查找仍按相关候选供用户判断。不要为了本次人工查找交付执行校准apply或伪造复核就绪。

## S2 隔离证据复核试验

S2 只比较两个固定候选。0.6B 重排候选使用自带的 C++ 适配器读取最终 token 位置的原始 `yes` / `no` logits；不能改用 llama.cpp 通用 rerank 接口或生成的 yes/no 字符串。构建命令：

```sh
sh scripts/build-reranker-logits.sh
```

4B 指令候选由独立 llama-server 提供受限 JSON 输出。服务固定为单槽、8K 上下文、非思考模式、关闭提示缓存和普通日志，并为模型摘要设置固定别名：

```sh
/opt/homebrew/bin/llama-server \
  -m "/absolute/path/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
  --alias 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597 \
  -c 8192 -b 8192 -ub 1024 -np 1 -n 384 \
  --reasoning off --chat-template-kwargs '{"enable_thinking":false}' \
  --no-cache-prompt --no-slots --log-disable \
  --host 127.0.0.1 --port 8767
```

测量数据必须放在独立测试目录，并显式列出每个问题经第一阶段召回得到的 1–40 个候选。该入口不会打开 `PKB_DATA_DIR`。固定格式为：

```json
{
  "passages": [
    {
      "id": "p1",
      "title": "合成资料标题",
      "text": "不超过 1200 字的合成片段",
      "content_version": 1,
      "qualification_version": 1
    }
  ],
  "queries": [
    {"id": "q1", "text": "合成问题", "candidates": ["p1"]}
  ]
}
```

两个候选须顺序运行，不能同时常驻或在一次失败后切换候选补结果：

```sh
python3 -m pkb.review_measure \
  --candidate reranker \
  --dataset /private/tmp/pkb-s2/calibration.json \
  --output /private/tmp/pkb-s2/reranker-report.json \
  --model "/absolute/path/Qwen3-Reranker-0.6B-Q8_0.gguf" \
  --reranker-executable "$PWD/build/qwen-reranker-logits"

python3 -m pkb.review_measure \
  --candidate instruct \
  --dataset /private/tmp/pkb-s2/calibration.json \
  --output /private/tmp/pkb-s2/instruct-report.json \
  --model "/absolute/path/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
  --port 8767
```

重排报告保存原始 logits 和两类归一化分数，但 `accepted` 保持 `null`，因为开发没有选择阈值。4B 只有 `supported` 且至少一条引文能在本次实际片段正文中逐字定位时才结构性通过。两条路径都先应用完整业务编号全匹配门禁，并把问题、证据、内容版本、资格版本、模型、量化、模板、配置和管线绑定进结果。该工具不做阈值选择、质量结论或正式启用；这些工作由独立测试、审计和用户验收完成。

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
