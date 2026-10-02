# 第三方组件与来源记录

更新时间：2026-10-02。本文记录本机安装或调用的直接第三方组件。项目仓库不包含模型文件、llama.cpp 二进制或 API 密钥。

## Qwen3-Embedding-0.6B Q8_0

- 用途：本地文本向量；不用于云端回答。
- 发布者：Qwen。
- 获取日期：2026-09-25；来源与许可复核日期：2026-09-26。
- 官方仓库：`https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF`
- 固定仓库修订：`370f27d7550e0def9b39c1f16d3fbaa13aa67728`
- 固定下载地址：`https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/370f27d7550e0def9b39c1f16d3fbaa13aa67728/Qwen3-Embedding-0.6B-Q8_0.gguf`
- 文件：`Qwen3-Embedding-0.6B-Q8_0.gguf`，639,150,592 字节。
- 文件及官方 LFS SHA256：`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`。
- 模型来源链：官方仓库元数据将基础模型列为 `Qwen/Qwen3-0.6B-Base`；官方模型卡将本文件列为 Qwen3-Embedding-0.6B 的 `q8_0` 量化版本，向量维度最高 1024、上下文上限 32K。
- 许可证：Apache License 2.0；以固定修订的仓库元数据与模型卡为依据。许可证文本：`https://www.apache.org/licenses/LICENSE-2.0`。
- 通知：保留 Qwen 发布者归属、仓库、固定修订、文件名、量化类型与许可证信息；不得将该文件描述为本项目原创模型。

下载或重新下载时必须使用固定修订地址，并在启动前核对文件大小和 SHA256。若官方仓库、文件摘要或许可证发生变化，应作为新组件重新评估，不能沿用本记录。

## Qwen3-Reranker-0.6B Q8_0（S2 试验）

- 用途：隔离数据上的本地问题—片段证据复核候选；尚未接入正式应用。
- 官方上游：`Qwen/Qwen3-Reranker-0.6B`，固定上游修订 `e61197ed45024b0ed8a2d74b80b4d909f1255473`。
- 官方上游 `model.safetensors` SHA256：`27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b`。
- 实际量化发布者与仓库：`ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF`，固定仓库修订 `a02f48bb4f057028298c21fa033da2b30d7742d5`；该修订包含文件上传提交 `ff8a9aa`，不得用可变 `main` 替代。
- 固定下载地址：`https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/a02f48bb4f057028298c21fa033da2b30d7742d5/qwen3-reranker-0.6b-q8_0.gguf`。
- 实际文件：`Qwen3-Reranker-0.6B-Q8_0.gguf`，639,153,184 字节，Q8_0。
- 实际文件 SHA256：`22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48`。
- 来源链：量化仓库声明基础模型为 `Qwen/Qwen3-Reranker-0.6B`，格式为 llama.cpp GGUF、量化为 Q8_0。发布仓库没有提供足以独立复现的完整转换工具提交和命令，因此本轮把该缺口显式交审计，不能把文件摘要一致描述成转换链已复现。
- 许可证：上游和量化仓库均标识 Apache License 2.0。

应用不会下载或更新该文件。适配器启动前按固定 SHA256 校验，使用模型官方 causal prompt 与最后位置的 `yes` / `no` token logits；通用 rank pooling 结果不作为该模型输出。

## Qwen3-4B-Instruct-2507 Q4_K_M（S2 试验）

- 用途：隔离数据上的本地结构化证据充分性复核候选；尚未接入正式应用。
- 官方上游：`Qwen/Qwen3-4B-Instruct-2507`；量化发布时记录的固定上游修订 `b79a0e62a051eebdd801742a4a70bbaac6b38747`。
- 实际量化发布者与仓库：`unsloth/Qwen3-4B-Instruct-2507-GGUF`，固定仓库修订 `3e772c15a5192f387bcdfc1d24341034bed9c22f`。
- 固定下载地址：`https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/3e772c15a5192f387bcdfc1d24341034bed9c22f/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`。
- 实际文件：`Qwen3-4B-Instruct-2507-Q4_K_M.gguf`，2,497,281,120 字节，Q4_K_M。
- 实际文件 SHA256：`3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`。
- 来源链：量化仓库声明基础模型为官方 Qwen3-4B-Instruct-2507，并发布 llama.cpp GGUF Q4_K_M 文件。发布记录未给出足以独立复现的完整转换工具提交和命令；本轮保留此供应链限制供审计裁定，不声称已本地重建量化。
- 许可证：官方上游和量化仓库均标识 Apache License 2.0。

查询阶段只连接显式启动的 `127.0.0.1` llama-server，不自动下载、执行远程代码、使用代理、跟随重定向或调用外部工具。

## llama.cpp 运行时

- 用途：在 `127.0.0.1` 提供本地向量/指令 HTTP 服务，并为 S2 重排适配器提供本地 C API 动态库。
- 获取日期：2026-09-25；来源与许可复核日期：2026-09-26。
- 上游：`ggml-org/llama.cpp`，`https://github.com/ggml-org/llama.cpp`。
- 安装来源：Homebrew/core `llama.cpp` 0.5.0；上游标签 `v0.5.0`，提交 `7fe450e19305b828c199d602c23a8337aaa1f03b`。
- Homebrew/core 公式快照：tap 提交 `873e7f53af3fa56336523d7adf31def3a58eb647`，公式 SHA256 `bb04944e50346d5eeb863d77b59ff4af5ffadd96b101828b5a97c46c42ac52a9`。
- 当前 arm64 Tahoe bottle SHA256：`1dea72a74612d3fab141d92220c8c4e5746cd25fede74636fdec8b915845d605`。
- 许可证：MIT。上游通知为 “Copyright (c) 2023-2026 The ggml authors”。本机许可证文件 SHA256：`94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`；上游文本：`https://github.com/ggml-org/llama.cpp/blob/7fe450e19305b828c199d602c23a8337aaa1f03b/LICENSE`。

当前 Homebrew 运行时依赖如下。它们由 Homebrew 安装，不随本项目仓库分发：

| 组件 | 版本 | 许可证 | 上游来源或发布包 SHA256 |
| --- | --- | --- | --- |
| ggml | 0.25.3 | MIT | `https://github.com/ggml-org/ggml`；源码包 `cd9b92d5652f5e4abb41603bf59e269f8fec1b2d05ce22fded981064dd25fb89` |
| libomp | 23.1.2 | Apache-2.0 WITH LLVM-exception | LLVM 23.1.2 源码包 `c98bbef08a2b4c2613cd50e9aa9ae7b69b1fe6c16b2c40373bc0ab6116fdf78a` |
| openssl@3 | 3.6.4 | Apache-2.0 | OpenSSL 3.6.4 源码包 `9bffaa1ad1e07b354c21bd3324ec02fa15579f45a7d0494b3e74bc449b7333ef` |
| ca-certificates | 2026-09-25 | MPL-2.0 | Mozilla CA bundle `a41b5d356aea97a529fe27e0f7316d2f9d946d75927476cf9cf1b90637d00505` |

libomp 的许可证及通知以 LLVM 23.1.2 的 `LICENSE.TXT` 为准，其中包含 Apache License 2.0 正文、LLVM Exceptions 以及所含第三方软件通知。本机文件 SHA256 为 `8d85c1057d742e597985c7d4e6320b015a9139385cff4cbae06ffc0ebe89afee`；固定上游入口：`https://github.com/llvm/llvm-project/blob/llvmorg-23.1.2/LICENSE.TXT`。

其余运行时依赖已逐项与本机安装内容复核：

- ggml 0.25.3 的本机 `LICENSE` 为 MIT，SHA256 `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`；固定上游入口：`https://github.com/ggml-org/ggml/blob/v0.25.3/LICENSE`。
- openssl@3 3.6.4 的本机 `LICENSE.txt` 为 Apache License 2.0，SHA256 `7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a`；固定上游入口：`https://github.com/openssl/openssl/blob/openssl-3.6.4/LICENSE.txt`。
- ca-certificates 2026-09-25 的本机 `cacert.pem` SHA256 为 `a41b5d356aea97a529fe27e0f7316d2f9d946d75927476cf9cf1b90637d00505`，与固定下载包摘要一致；Homebrew SPDX SBOM 将许可证结论记录为 MPL-2.0。该 SBOM 的 SHA256 为 `43857df969e708b7d93dd2e02c8084cb9dbb649d5f4d01fcba8dc60b61da220f`，文档命名空间为 `https://formulae.brew.sh/spdx/ca-certificates-2026-09-25.json`。

## DeepSeek 官方 API

DeepSeek 是运行时外部服务，不是随项目分发的软件组件。固定接收地址为 `https://api.deepseek.com/chat/completions`。适用文件入口：

- 开放平台服务条款：`https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html`
- 隐私政策：`https://cdn.deepseek.com/policies/zh-CN/deepseek-privacy-policy.html`

项目不宣称 API 零留存或一律不用于训练；每次请求仍须按产品规则展示实际内容并单独确认。
