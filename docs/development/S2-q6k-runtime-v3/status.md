# Q6_K 既有 CPython 3.12.13 只读来源调查 v3

日期：2026-10-18（Asia/Shanghai）。产品确定的优先级是调查既有解释器，未批准将其用于构建。本轮结论：**发布者的预期发行件已精确对应，当前安装完整性仍未闭合；现有 pip 有 9 项 RECORD 不一致，继续 `approval_blocked`。** 未修复、安装、构建、转换或启动模型，未运行产品/模型测试。

保留 v2 提交 `83c5b5c2185f7515d85dc37ac039614827bb67a8` 的全部字节及原始证据。产品代码 `391baf9db5afcffd8e2de4ba65782a05b6426a98`、独立测试包和 oracle 均未修改。

## 可核对的本机身份与发布者映射

本机真实路径是 `/Users/allenqiu/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/bin/python3.12`，只以 `-I -S` 读取标准库版本/配置。观察到 CPython 3.12.13、arm64、SOABI `cpython-312-darwin`；构建日期 2026-06-23，构建编译器 Clang 22.1.3。

| 本机文件 | 字节数 | 当前 SHA-256 |
| --- | ---: | --- |
| `bin/python3.12` | 18,073,888 | `7b05d803bbc1bbfc81644af4faf2b88f0a37b8de96b9f42c1e08033e2cd0848a` |
| `lib/libpython3.12.dylib` | 18,073,728 | `ed96948e89d9bdd08250fa0dcc700d8b7ed95a58c6adf7a457a956b5b09ee20b` |
| `/Users/allenqiu/.local/bin/uv` | 50,659,616 | `c9300ed8425e2c85230259a172066a32b475bc56f7ebe907783b2459159ea554` |

本机 `BUILD` 文本为 `20260623`。browser-harness 的 pyvenv.cfg 记录由 uv 0.11.26、CPython 3.12.13 建立；其 uv-receipt 只声明需要 Python 3.12，不含解释器发行件校验值。本机 `/Users/allenqiu/.config/uv/uv-receipt.json` 记录 GitHub/astral-sh/uv、版本 0.11.26、cargo-dist 安装前端和安装目录，未提供本机 uv 文件对应的发行摘要。以上原文和摘要在 `raw/` 与 `runtime-inventory.json`。

只读 `git ls-remote` 将 uv 0.11.26 标签映射到 `396ef7ce44e343095f3a5a5e8bc4b0b670ed0f5b`，与本机 uv --version 的短提交一致。该固定提交的[官方 Python 下载元数据](https://raw.githubusercontent.com/astral-sh/uv/396ef7ce44e343095f3a5a5e8bc4b0b670ed0f5b/crates/uv-python/download-metadata.json) 对应：

- 发行件：`cpython-3.12.13+20260623-aarch64-apple-darwin-install_only_stripped.tar.gz`。
- [精确官方来源](https://github.com/astral-sh/python-build-standalone/releases/download/20260623/cpython-3.12.13%2B20260623-aarch64-apple-darwin-install_only_stripped.tar.gz)。
- HEAD 大小：**25,003,823 字节**；发布摘要：`41df7d3ae4757e84b97874f76d634268456aaa271740d33f968d826374998fb7`。

uv 自身的[官方 dist-manifest](https://github.com/astral-sh/uv/releases/download/0.11.26/dist-manifest.json) 与[归档校验和](https://github.com/astral-sh/uv/releases/download/0.11.26/uv-aarch64-apple-darwin.tar.gz.sha256) 均将 arm64 macOS 发行归档固定为 SHA-256 `8f7fbf1708399b921857bce71e1d60f0d3ccf52a30caebc1c1a2f175dce13ab6`；manifest 列出 uv/uvx 资产，但未给出归档内 uv 可执行文件的独立摘要，linkage 列表为空。

**未证明点：** 版本、BUILD、目录及 receipt 能对应发布者预期来源，但没有带可信摘要的原始解释器安装凭据或发布者逐文件基线，不能把本机可执行文件摘要直接与归档摘要比较。uv 本机二进制同样缺归档内文件基线。只读 codesign display 显示这三个本机二进制均为 ad-hoc、无 TeamIdentifier；不能当作发布者身份签名。

## 已有安装前端 pip 的证据与不一致

本机 pip 26.1.2 的 INSTALLER 为 pip；direct_url.json 指向一次临时本地 wheel，记录 SHA-256 `382ff9f685ee3bc25864f820aa50505825f10f5458ffff07e30a6d96e5715cab`。该摘要与 [PyPI 固定版本 JSON](https://pypi.org/pypi/pip/26.1.2/json) 中 `pip-26.1.2-py3-none-any.whl` 一致，公开发行件 **1,813,144 字节**。本机 METADATA 与官方索引摘要校验后的 PEP 658 sidecar 完全相同；vendor.txt 与固定 PyPA 版本源文件相同。

对本机 RECORD 声明的文件做只读摘要/大小核对：470 个有摘要文件，0 缺失，**9 个不一致**，另有 396 项无摘要（RECORD 自身及 pyc 等）。具体预期/实际大小、摘要及启动脚本文字在 `pip-record-mismatches.json`：

- `bin/pip`、`bin/pip3`、`bin/pip3.12`：RECORD 为 252 字节，当前为 234 字节；当前脚本使用相对解释器定位。
- `pip/_vendor/distlib/` 下 `t32.exe`、`t64-arm.exe`、`t64.exe`、`w32.exe`、`w64-arm.exe`、`w64.exe`：大小与 RECORD 相同，SHA-256 不一致。

本轮不推断修改原因，不将平台不适用的 launcher 排除后伪称 RECORD 全通过，也没有修复或覆盖文件。RECORD 自身是本地可改记录；即使全部匹配也不是发布者逐文件基线。当前不批准复用该 pip 或 uv 作为构建/安装前端。

## 动态依赖与许可边界

`native-inventory.json` 记录解释器、libpython、现有 `.dylib`/`.so` 共 11 个去重后的 native 输入摘要，并保存 otool -L 和 file 原始输出。可见 Tcl/Tk、itcl、thread 等附带本地库，以及 macOS 系统库引用。此为静态 Mach-O 加载声明与当前文件快照；没有加载这些扩展、没有运行模型，也不声称覆盖运行时所有 dlopen 路径、系统共享缓存或完整标准库的发布者完整性。

本机 CPython 根 LICENSE 与 [CPython v3.12.13 官方文本](https://raw.githubusercontent.com/python/cpython/v3.12.13/LICENSE) 逐字一致；uv 固定版本的 MIT/Apache 文本已保存。`local-license-inventory.json` 保存 23 份现有许可文本及摘要，其中 22 份是 pip METADATA 声明的许可文件，声明路径均能找到。当前安装目录中额外定位到的 runtime 根许可只有 CPython LICENSE，没有据此闭合 Tcl/Tk 等捆绑组件和静态链接依赖的许可。pip 声明包含 MIT 及 vendored 组件许可，不能简化成“整个工具链都是 MIT”。发布者完整捆绑组件清单/许可、SPDX 标准化继续待审。

## v2 对照及预算变化

`v2-to-v3-delta.json` 绑定已有独立审计 `docs/audit/S2-q6k-metadata-v2-review-20261018/independent-check.json` 的原始摘要。该审计已验证相同 28 个 wheel 的 3.12.15→3.12.13 Requires-Python 与 32 条激活边没有差异，本轮复用该结论，没有重新联网收集闭包或重跑相同求解。

本轮实际观察到 macOS **26.6.2 / build 25G83**，SDK **26.5**，Apple Clang **21.0.0 (clang-2100.1.1.101)**，CLT **26.6.0.0.1781586589**。与 packaged Python 自身的 Clang 22.1.3 区分。仅增量核对原 28 个 wheel tag 对当前主机仍兼容；wheel 集合及 **119,388,505 字节**不变。

预算只列条件差异，不形成资源申请：

| 未来路线，均需另经审查/授权 | 本轮能够给出的下载差异 |
| --- | ---: |
| 复用现有解释器且来源完整性获准 | 理论新增解释器下载 0 字节；目前该前提不成立 |
| 新隔离目录取得上述精确官方解释器归档作为干净比较/替换来源 | 25,003,823 字节 |
| 若另选上述干净 pip wheel 作为安装前端 | 再加 1,813,144 字节 |

后两项相加 **26,816,967 字节**，仅为具体备选来源的网络差额。归档展开量、工具源码传输、完整安装/构建依赖、许可及总预算仍未闭合；不能把这项差额或 v2 小计作为额度请求。没有自动获取上述归档或 wheel，也没有创建新的 runtime/venv。

## 交产品及审计的剩余决策

1. 现有解释器与 uv 发行件映射得到佐证，但缺可信安装/逐文件基线；pip 又有 9 项实际 RECORD 差异，当前复用路线不能按“来源已过”推进。
2. 产品可决定是否继续寻找既有可信基线，或将上表精确官方归档/干净 pip 作为后续候选来源。后者仍须按独立审批阶段审查，不代表本次获准下载、安装或修复现有工具。
3. 源码获取的精确大小/摘要、完整构建 argv/cache/env、bootstrap 和捆绑许可仍保留阻断。既有计划只固定 Release、量化目标及 -j 4，不能把当前未决定的 runtime/front-end 路径冒写成已冻结 argv。
4. 所有新构建产物摘要/动态库验证仍在未来获准构建后、转换/启动前由审计检查；本轮没有提前声称通过。

采集脚本和 stdout/stderr 在本目录保留；只读 native 检查脚本及命令/输出也已保存。网络回执只涉及官方 JSON、文本许可/校验和、PEP 658 文本和 archive HEAD，artifact 正文传输记录为 0；不是独立网络取证。此次交付不代表真实 reviewer 来源/质量、实际向量检索、HTTP/UI 或资源验收通过。
