# 🎙️ 语音输入法 (Voice Input Method)

> 按住热键说话，松开自动识别并输入文字 — 离线、快速、精准的中文语音输入工具

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)

## ✨ 效果演示

```
PS D:\qiniuyun\qiniuyun-test> voice-input --no-gui
这是一个语音输入法。🎤 ⠹ 录音中 ...
喂喂喂，能听到吗
```

按住 **F9** 说话 → 松开自动识别 → 文字直接输入到光标位置

## 🚀 快速开始

### 环境要求

- **Python 3.10+**（推荐 3.12）
- **Windows 10/11**
- **ffmpeg**（可选，用于音频处理）

### 一键安装

```bash
# 克隆项目
git clone <your-repo-url>
cd qiniuyun-test

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖（FunASR 后端 + 热键支持）
pip install -e ".[funasr,hotkey]"

# 安装键盘模拟（用于自动打字输出）
pip install keyboard

# 启动
voice-input --no-gui
```

### 使用方式

| 操作 | 说明 |
|------|------|
| **按住 F9** | 开始录音 |
| **松开 F9** | 停止录音，自动识别并输入 |
| **Alt+R** | 切换长录音模式（开发中） |
| **Ctrl+C** | 退出程序 |

识别结果会同时：**① 自动打字到光标处 ② 复制到剪贴板**

## 🏗️ 技术栈

### 核心框架

| 技术 | 用途 | 版本 |
|------|------|------|
| **FunASR** | 语音识别引擎（SenseVoiceSmall） | ≥1.0.0 |
| **PyTorch** | FunASR 的推理后端 | ≥2.0.0 |
| **pynput** | 全局热键监听 | ≥1.7.6 |
| **keyboard** | 键盘模拟打字 | ≥0.13.5 |
| **sounddevice** | 音频录制 | ≥0.4.6 |
| **numpy** | 音频数据处理 | ≥1.24.0 |
| **PyYAML** | 配置文件解析 | ≥6.0 |
| **pydantic** | 数据校验 | ≥2.0.0 |

### 架构设计

```
src/voice_input/
├── __main__.py          # 入口，简洁终端UI
├── engine.py            # 核心状态机引擎
├── config.py            # 配置管理（YAML + Dataclass）
├── protocols.py         # 接口协议定义
│
├── asr/                 # ASR 语音识别层（可插拔后端）
│   ├── base.py          # 抽象基类
│   ├── funasr_backend.py # FunASR/SenseVoice 后端 ⭐
│   ├── sherpa_backend.py # sherpa-onnx 后端
│   └── cloud_backend.py  # 云端API后端（预留）
│
├── audio/               # 音频处理层
│   ├── recorder.py      # 麦克风录音
│   └── vad.py           # 语音活动检测
│
├── hotkey/              # 热键监听层
│   └── listener.py      # PTT/Toggle 热键
│
├── output/              # 输出层
│   ├── clipboard.py     # 剪贴板输出
│   └── typer.py         # 键盘打字输出
│
├── text/                # 文本后处理
│   ├── processor.py     # 文本清理/规范化
│   └── hotwords.py      # 热词管理 & 纠正
│
└── gui/                 # GUI 层（预留）
    └── tray.py          # 系统托盘
```

### 设计模式

- **协议驱动**：`ASRBase` 抽象基类，后端可插拔切换
- **状态机引擎**：`IDLE → RECORDING → PROCESSING` 三态流转
- **异步架构**：`asyncio` 驱动，不阻塞 UI
- **配置驱动**：`config.yaml` 统一管理所有参数

## 📋 功能特性

- ✅ **离线语音识别** — 无需联网，本地模型推理
- ✅ **多语言支持** — 中文/英文/日文/韩文/粤语（SenseVoice）
- ✅ **智能标点** — SenseVoice 自带逆文本规范化（数字→中文）
- ✅ **热词纠错** — 支持自定义热词映射表
- ✅ **双通道输出** — 剪贴板 + 键盘打字同时输出
- ✅ **PTT 按键对讲** — 按住说话，松开识别
- ✅ **静默启动** — 无冗余日志，极简终端输出

## ⚙️ 配置说明

编辑 `config.yaml` 自定义行为：

```yaml
asr:
  backend: "funasr"           # 后端: funasr / sherpa / cloud
  funasr:
    model: "d:/path/to/model"  # 本地模型路径
    language: "zh"             # 语言: zh / en / ja / ko / auto

hotkey:
  ptt_key: "f9"                # 录音热键
  mode: "ptt"                  # ptt(按住说) / toggle(切换)

output:
  mode: "both"                 # both / clipboard / typing
```

## 🔧 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check src/
```

## 📖 开发过程与问题解决

详见 [pr和commit.md](./pr和commit.md) — 完整记录了三天开发周期中的每个阶段、遇到的问题及解决方案。

## 📄 License

MIT License

## 🙏 致谢

- [FunASR / SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里达摩院语音识别模型
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) — Kaldi 团队 ONNX 推理引擎
- [ModelScope](https://www.modelscope.cn) — 魔搭社区模型托管
