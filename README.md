# 🎙️ 语音输入法 (Voice Input Method)

> 按住热键说话，松开自动识别并输入文字 — 离线、快速、精准的中文语音输入工具

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)

## ✨ 效果演示

```
PS D:\qiniuyun\qiniuyun-test> python -m voice_input --no-gui
正在启动语音输入法...funasr version: 1.3.1.
  ⏳ 加载模型中 (约需10-20秒，请耐心等待)...
✅ 启动完成!  (按 F9 开始录音, Ctrl+C 退出)
  🎤 ⠹ 录音中 ...
喂喂喂，能听到吗
hello world
5号5号
```

按住 **F9** 说话 → 松开自动识别 → 文字直接输入到光标位置

## 🚀 快速开始

### 环境要求

- **Python 3.10+**（推荐 3.12）
- **Windows 10/11**
- **GPU**（可选，CPU 也可运行但较慢）

### 一键安装

```bash
# 克隆项目
git clone https://github.com/crazy-hajime/qiniuyun-test.git
cd qiniuyun-test

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖（FunASR 后端 + 热键支持）
pip install -e ".[funasr,hotkey]"

# 安装键盘模拟（用于自动打字输出）
pip install keyboard soundfile

# 首次运行：下载模型（约 900MB）
python -m voice_input --no-gui -v
```

### 启动方式（二选一）

**方式 1：模块方式（推荐）**
```bash
cd d:\qiniuyun\qiniuyun-test
python -m voice_input --no-gui
```

**方式 2：直接运行文件**
```bash
d:\qiniuyun\.venv\Scripts\python.exe d:\qiniuyun\qiniuyun-test\src\voice_input\__main__.py --no-gui
```

### 使用方式

| 操作 | 说明 |
|------|------|
| **按住 F9** | 开始录音（PTT 按键对讲模式） |
| **松开 F9** | 停止录音，自动识别并输入 |
| **Alt+R** | 切换长录音模式（Toggle 模式） |
| **Ctrl+C** | 安全退出程序 |

识别结果会同时：**① 自动打字到光标处 ② 复制到剪贴板**

### 启动流程说明

```
T=0s    正在启动语音输入法...funasr version: 1.3.1.
T=1s    ⏳ 加载模型中 (约需10-20秒，请耐心等待)...   ← 等待中，不要按键
T=15s   ✅ 启动完成!  (按 F9 开始录音, Ctrl+C 退出)    ← 可以使用了
```

> ⚠️ **重要**: 模型加载期间（显示 ⏳ 时）请勿触碰键盘或鼠标，否则可能触发中断。

## 🏗️ 技术栈

### 核心框架

| 技术 | 用途 | 版本 |
|------|------|------|
| **FunASR** | 语音识别引擎（SenseVoiceSmall） | ≥1.0.0 |
| **PyTorch** | FunASR 的推理后端 | ≥2.0.0 |
| **pynput** | 全局热键监听 | ≥1.7.6 |
| **keyboard** | 键盘模拟打字 | ≥0.13.5 |
| **soundfile** | WAV 音频文件写入 | ≥0.12.0 |
| **sounddevice** | 麦克风录音（延迟导入） | ≥0.4.6 |
| **numpy** | 音频数据处理 | ≥1.24.0 |
| **PyYAML** | 配置文件解析 | ≥6.0 |
| **pydantic** | 数据校验 | ≥2.0.0 |

### 性能优化

| 优化项 | 方案 | 效果 |
|--------|------|------|
| ASR 后端导入 | 延迟导入 (lazy import) | 60s → 0.12s |
| 音频设备初始化 | sounddevice 延迟到录音时加载 | 5-30s → 0ms |
| WAV 写入 | scipy → soundfile | 10-60s → <1ms |
| **总启动时间** | **以上优化叠加** | **∞(卡死) → ~15s** |

### 架构设计

```
src/voice_input/
├── __main__.py          # 入口，简洁终端UI + 友好错误提示
├── engine.py            # 核心状态机引擎 (IDLE→RECORDING→PROCESSING)
├── config.py            # 配置管理 (YAML + Pydantic Dataclass)
├── protocols.py         # 接口协议定义 (ASRBase, ASRResult)
│
├── asr/                 # ASR 语音识别层（可插拔后端，延迟导入）
│   ├── __init__.py      # 延迟导入工厂，按需加载后端 ⭐
│   ├── base.py          # 抽象基类
│   ├── funasr_backend.py # FunASR/SenseVoice 后端 (默认)
│   ├── sherpa_backend.py # sherpa-onnx 后端
│   └── cloud_backend.py  # 云端API后端（预留）
│
├── audio/               # 音频处理层
│   ├── recorder.py      # 麦克风录音 (sounddevice 延迟导入)
│   └── vad.py           # 语音活动检测 (VAD)
│
├── hotkey/              # 热键监听层
│   └── listener.py      # PTT/Toggle 热键 (pynput, 防重复触发)
│
├── output/              # 输出层
│   ├── clipboard.py     # 剪贴板输出 (pyperclip)
│   └── typer.py         # 键盘打字输出 (keyboard)
│
├── text/                # 文本后处理
│   ├── processor.py     # 文本清理/规范化
│   └── hotwords.py      # 热词管理 & 纠正
│
└── gui/                 # GUI 层（预留）
    └── tray.py          # 系统托盘 (PyQt6)
```

### 设计模式

- **协议驱动**：`ASRBase` 抽象基类，后端可插拔切换
- **延迟导入**：ASR 后端和 sounddevice 按需加载，优化启动速度
- **状态机引擎**：`IDLE → RECORDING → PROCESSING` 三态流转
- **信号处理**：自定义 SIGINT 处理器，友好处理 Ctrl/C 中断
- **配置驱动**：`config.yaml` 统一管理所有参数

## 📋 功能特性

- ✅ **离线语音识别** — 无需联网，本地模型推理
- ✅ **多语言支持** — 中文/英文/日文/韩文/粤语（SenseVoice）
- ✅ **智能标点** — SenseVoice 自带逆文本规范化（数字→中文）
- ✅ **热词纠错** — 支持自定义热词映射表 (`hotwords.txt`)
- ✅ **双通道输出** — 剪贴板 + 键盘打字同时输出
- ✅ **PTT 按键对讲** — 按住说话，松开识别
- ✅ **快速启动** — ~15秒启动（含模型加载），无冗余日志
- ✅ **友好错误提示** — 分步异常捕获，清晰的错误信息
- ✅ **中文路径兼容** — 自动处理含中文的 Windows 用户名路径

## ⚙️ 配置说明

编辑 `config.yaml` 自定义行为：

```yaml
asr:
  backend: "funasr"           # 后端: funasr / sherpa / cloud
  funasr:
    model: "d:/path/to/model"  # 本地模型路径 (SenseVoiceSmall)
    language: "zh"             # 语言: zh / en / ja / ko / auto
    enable_punctuation: true    # 自动添加标点

hotkey:
  ptt_key: "f9"                # 录音热键 (F9)
  toggle_key: "alt_r"           # 切换模式热键 (Alt+R)
  mode: "ptt"                  # ptt(按住说) / toggle(切换)

output:
  mode: "both"                 # both / clipboard / typing
  typing_delay: 0.02            # 打字间隔 (秒)

audio:
  sample_rate: 16000           # 采样率
  silence_duration: 1.5         # 静音检测阈值 (秒)
  max_duration: 60             # 最长录音时长 (秒)
```

## 🔧 故障排除

### 常见问题

#### Q1: 启动后卡在 "正在启动..." 无响应

**原因**: FunASR 模型正在加载 (~893MB)，需要 10-20 秒。

**解决**: 
- 耐心等待 `✅ 启动完成!` 出现
- 加载期间**不要触碰键盘**
- 如果超过 30 秒仍未完成，用 `-v` 参数查看详细日志：
  ```bash
  python -m voice_input --no-gui -v
  ```

#### Q2: 按 F9 没有反应

**检查清单**:
1. 确认看到 `✅ 启动完成!` 提示
2. 尝试其他键位（如 F8）：修改 `config.yaml` 的 `ptt_key`
3. 以管理员身份运行终端

#### Q3: 报错 "KeyboardInterrupt"

**原因**: 模型加载期间按了 Ctrl/C 或触碰键盘。

**解决**: 重新运行并等待 15 秒不要操作。

#### Q4: 识别结果为空或不准确

**解决**:
- 确保麦克风权限已开启
- 调整 `silence_duration` 参数（默认 1.5 秒太短会截断语音）
- 检查 `language` 设置是否匹配你的语言

#### Q5: 中文路径报错 (sentencepiece)

**症状**: `OSError: Not found: ...罗欣...bpe.model`

**原因**: Windows 用户名含中文，sentencepiece 不支持非 ASCII 路径。

**解决**: 已自动处理 — 模型会被复制到 `%TEMP%\voice-input-models\` 目录。

#### Q6: GitHub 推送失败 (443 超时)

**原因**: 国内网络访问 GitHub 不稳定。

**解决**:
- 配置代理：`git config --global http.proxy http://127.0.0.1:7890`
- 或使用 SSH 方式：`git remote set-url origin git@github.com:user/repo.git`

## 🔧 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码格式化
ruff check src/

# 诊断测试（逐步排查启动问题）
python test_step.py
```

## 📖 开发过程与问题解决

详见 [pr和commit.md](./pr和commit.md) — 完整记录了三天开发周期中的每个阶段、遇到的问题及解决方案。

## � 版本历史

### v0.1.0 (2026-05-23)

**Day 1 — 项目骨架搭建**
- 初始化项目结构、配置体系、状态机引擎
- 实现音频录制 (VAD)、全局热键 (PTT/Toggle)、双通道输出

**Day 2 — ASR 语音识别集成**
- 集成 sherpa-onnx 后端（初始方案）
- 切换至 FunASR 后端（最终方案，兼容性更好）
- 修复热键重复触发、配置加载嵌套问题

**Day 3 — 体验优化与工程化**
- 极简终端输出（隐藏噪音日志）
- 中文路径兼容性修复
- 完善 README 与开发文档

**Bug Fix — 启动卡顿修复 (#1 PR)**
- 修复启动无限等待问题（~60s → ~15s）
- 延迟导入 ASR 后端、sounddevice、scipy→soundfile
- 友好处理 KeyboardInterrupt

**Bug Fix — KeyboardInterrupt 友好处理**
- 添加模型加载进度提示
- 自定义 SIGINT 信号处理器
- 区分用户中断 vs 真正错误

## �📄 License

MIT License

## 🙏 致谢

- [FunASR / SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里达摩院语音识别模型
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) — Kaldi 团队 ONNX 推理引擎
- [ModelScope](https://www.modelscope.cn) — 魔搭社区模型托管
- [sounddevice](https://python-sounddevice.readthedocs.io/) — 音频录制库
- [pynput](https://pynput.readthedocs.io/) — 全局热键库
