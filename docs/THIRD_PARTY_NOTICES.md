# 第三方组件与来源记录

更新时间：2026-09-26。本文记录 V1.1 本机安装或调用的直接第三方组件。项目仓库不包含模型文件、llama.cpp 二进制或 API 密钥。

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

## llama.cpp 运行时

- 用途：在 `127.0.0.1` 提供本地向量 HTTP 服务。
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

## DeepSeek 官方 API

DeepSeek 是运行时外部服务，不是随项目分发的软件组件。固定接收地址为 `https://api.deepseek.com/chat/completions`。适用文件入口：

- 开放平台服务条款：`https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html`
- 隐私政策：`https://cdn.deepseek.com/policies/zh-CN/deepseek-privacy-policy.html`

项目不宣称 API 零留存或一律不用于训练；每次请求仍须按产品规则展示实际内容并单独确认。
