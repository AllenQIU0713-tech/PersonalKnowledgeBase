# S2 已批准模型可复现量化来源补全方案

日期：2026-10-03。范围只包括已批准的 `Qwen3-Reranker-0.6B` 与 `Qwen3-4B-Instruct-2507`，不增加第三模型，不在本阶段下载或执行转换。

## 现状核实

- 已有试验 GGUF：0.6B Q8_0 639,153,184 字节；4B Q4_K_M 2,497,281,120 字节；均已固定 SHA256。
- 本机 Homebrew llama.cpp 为 0.5.0 / commit `7fe450e19305b828c199d602c23a8337aaa1f03b`，已有 `/opt/homebrew/bin/llama-quantize`。
- Homebrew 安装不含 `convert_hf_to_gguf.py`；本机也没有两个官方模型的 safetensors、tokenizer/config 完整快照。
- 当前量化发布仓库声明了基础模型和量化类型，但没有提供足以从固定上游独立重建现有 GGUF 的完整工具提交、命令和参数。现有文件可继续隔离比较，不能据此通过最终供应链审计。
- 当前磁盘可用约 655 GiB，现有模型目录约 3.5 GiB，空间不是阻断项。

## 建议处置

如果未来测试选中某个候选，使用官方固定上游权重和固定 llama.cpp 源码在本机生成一个新的“项目重建 GGUF”。新文件摘要将成为正式候选摘要。它不应被宣称与当前第三方量化文件逐字相同；模型文件变化后必须重跑该候选的质量、稳定性、性能和最终全链路证据。

未选中的候选不做昂贵重建。这样既关闭最终入选模型的来源链，又避免提前下载约 10 GiB 原始权重和生成无用中间文件。

2026-10-03 独立初筛结果：0.6B 与 4B 均未满足硬性质量要求，没有最终入选候选。因此本方案当前不触发：不下载官方原始权重、不重建量化、不修改代码摘要，也不因来源链工作继续测试失败候选。本文保留为产品批准新路线后评估同一模型产物时的可审查参考。

## 固定输入与工具

### 共同工具链

- llama.cpp 源码提交：`7fe450e19305b828c199d602c23a8337aaa1f03b`。
- 转换脚本：该提交的 `convert_hf_to_gguf.py` 与同仓库 `gguf-py`。
- Python 依赖使用独立虚拟环境并锁定。该提交要求至少：`torch==2.11.0`、`numpy~=2.2.6`、`sentencepiece>=0.1.98,<0.3.0`、`transformers==4.57.6`、`gguf>=0.1.0`、`protobuf>=4.21.0,<5.0.0`。实际安装后保存完整 lock、wheel SHA256 和许可证清单。
- 量化程序：同一提交构建出的 `llama-quantize`；虽然本机 Homebrew 二进制来自同一提交，正式重建建议从固定源码构建转换脚本和量化器，并记录编译器、CMake 参数、二进制 SHA256。
- 禁止 `--remote` 转换、模型仓库代码执行、`trust_remote_code`、动态 `main/latest`、代理到非批准服务或上传任何用户资料。

### 0.6B 候选

- 官方仓库：`Qwen/Qwen3-Reranker-0.6B`。
- 固定官方修订：`e61197ed45024b0ed8a2d74b80b4d909f1255473`。
- 官方 `model.safetensors` 已记录 SHA256：`27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b`。
- 下载白名单：`model.safetensors`、`config.json`、`generation_config.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.json`、`merges.txt`、官方许可证/README 及模型卡需要的 sentence-transformers 配置。逐文件记录固定 URL、字节数、SHA256。
- 建议转换：直接由官方 BF16 safetensors 生成 Q8_0 GGUF，命令固定为 `convert_hf_to_gguf.py <snapshot> --outfile <output> --outtype q8_0`。这样不产生额外 BF16 GGUF；如果固定转换器对该模型的 direct Q8_0 不兼容，再改为 BF16 GGUF + `llama-quantize ... Q8_0`，并把路线变化交审计。
- 预计新增下载约 1.2 GiB；输出约 0.64 GiB；连同源码、venv、日志和双份核验预留 5 GiB。

### 4B 候选

- 官方仓库：`Qwen/Qwen3-4B-Instruct-2507`。
- 固定官方修订：`b79a0e62a051eebdd801742a4a70bbaac6b38747`；执行前先确认该修订仍可获取，并逐文件记录摘要，不能自动替换为当前 `main`。
- 下载白名单：3 个官方 safetensors 分片、`model.safetensors.index.json`、config/generation/tokenizer/vocab/merges、许可证和 README。禁止下载适配器、演示程序或执行仓库代码。
- 建议转换两步：`convert_hf_to_gguf.py <snapshot> --outfile <bf16.gguf> --outtype bf16`，随后 `llama-quantize <bf16.gguf> <q4_k_m.gguf> Q4_K_M`。不使用 importance matrix、重量化、tensor override 或未记录的默认变化。
- 预计官方 BF16 权重约 8.1 GiB，中间 BF16 GGUF 约 8.1 GiB，Q4_K_M 输出约 2.5 GiB；加源码、venv、日志与安全余量预留 25 GiB。当前约 655 GiB 可用。

## 执行产物

重建时必须生成一个只含技术来源、不含用户资料的 manifest：

```json
{
  "official_repo": "...",
  "official_revision": "40-hex",
  "input_files": [{"path": "...", "bytes": 0, "sha256": "64-hex"}],
  "llama_cpp_revision": "40-hex",
  "converter_sha256": "64-hex",
  "quantizer_sha256": "64-hex",
  "python_lock_sha256": "64-hex",
  "commands": ["argv array without shell interpolation"],
  "environment": {"macos": "...", "arch": "arm64", "compiler": "..."},
  "output": {"quant": "...", "bytes": 0, "sha256": "64-hex"},
  "licenses": [{"component": "...", "spdx": "...", "sha256": "64-hex"}]
}
```

命令应作为 argv 数组记录，输出目录使用新隔离路径；不覆盖当前测试 GGUF。转换日志不得包含环境凭证或用户路径以外的个人资料。完成后用 `llama-gguf`/`llama-gguf-hash` 读取元数据，并由审计复核模型架构、量化类型、chat template/tokenizer 与上游一致。

第一次构建完成后，必须在新的干净临时目录仅使用同一已核验输入、源码、依赖锁和命令完整重放第二次。两次最终 GGUF 的 SHA256 必须相同。若固定工具写入可解释的非确定字段，先列出字段和来源，再由审计批准规范化内容哈希或逐张量摘要；不能自行降低为“文件可加载”或“推理结果相似”。manifest 增加 `replay` 字段，至少记录第二目录、命令摘要、输出 SHA256 与比较结论。

## 审批与停止点

1. 独立测试已给出两个候选均淘汰的证据；现在不下载官方原始权重。
2. 若 0.6B 入选，只执行 0.6B 重建；若 4B 入选，只执行 4B 重建；若两者均失败，不执行量化补全，也不下载第三模型。
3. 执行前把精确下载清单、预计字节数、固定 URL、落盘目录和删除策略交用户/产品审查。下载只含公开模型和工具，不含用户资料。
4. 新 GGUF 生成并完成干净目录第二次重放后，先做摘要与静态元数据核验，再交独立测试重新运行所有模型相关已知回归、盲测、稳定性、资源和边界证据。旧测试结果只能说明旧 GGUF，不能移植到新摘要；代码、`THIRD_PARTY_NOTICES`、运行参数和模型摘要须切换到自建产物。
5. 新候选通过后才允许进入正式集成；供应链、质量、资源任一失败都继续保持 `calibration_required`。

## 尚待核实但不应猜测的项目

- 4B 固定修订三个分片的逐文件字节数和 SHA256；需要在批准下载前从固定修订元数据取得并写入清单。
- 固定源码构建的 `llama-quantize` 是否与 Homebrew bottle 产出相同二进制；正式链只要求工具来源和结果可复现，不假设二进制逐字相同。
- direct Q8_0 转换对 reranker 特有 tokenizer/chat template 的完整保留；需用静态 GGUF 元数据和随后真实 logits 回归确认。

本方案采用审计文件 `docs/audit/S2-quantization-provenance-closeout.md` 的最小关闭条件；若审计后续收紧，以审计条件为准。
