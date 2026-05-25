# 语音输入法 (Voice Input Method)

> 按住热键说话，松开自动识别并输入文字 — 离线、快速、精准的中文语音输入工具

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)

## 效果演示

```
PS D:\qiniuyun\qiniuyun-test> python -m voice_input
  加载模型中......
funasr version: 1.3.1.
启动完成! | 流式识别  (按 F9 开始录音, Ctrl+C 退出)
  录音中...
  流式识别能听到吗
→ 流式识别能听到吗
```

按住 **F9** 说话 → 实时显示识别文字 → 松开自动输入到光标位置

## 快速开始

### 环境要求

- **Python 3.10+**（推荐 3.12+）
- **Windows 10/11**
- **NVIDIA GPU**（可选，CPU 也可运行）

### 安装

```bash
# 克隆项目
git clone https://github.com/crazy-hajime/qiniuyun-test.git
cd qiniuyun-test

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install funasr torch torchaudio
pip install pynput keyboard soundfile sounddevice numpy pyyaml pyperclip scipy

# 首次运行：下载模型（约 900MB）
python -m voice_input -v
```

### 启动

```bash
python -m voice_input
```

### GPU 加速（可选）

默认使用 CPU 推理，安装 CUDA 版 PyTorch 可启用 GPU 加速：

```bash
# 卸载 CPU 版本，安装 CUDA 版本（约 2.6GB）
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 --force-reinstall
```

启动后如果检测到 GPU，会自动显示：
```
启动完成! | 流式识别 | GPU (NVIDIA RTX 3050, 4GB)  (按 F9 开始录音, Ctrl+C 退出)
```

### 使用方式

| 操作 | 说明 |
|------|------|
| **按住 F9** | 开始录音（PTT 按键对讲模式） |
| **松开 F9** | 停止录音，自动识别并输入 |
| **Alt+R** | 切换长录音模式（Toggle 模式） |
| **Ctrl+C** | 安全退出程序 |

识别结果会同时：**自动打字到光标处 + 复制到剪贴板**

### 命令行参数

```bash
python -m voice_input [选项]

选项:
  --config, -c     配置文件路径
  --verbose, -v    显示详细日志
  --no-gui         无GUI模式
  --backend, -b    ASR后端 (funasr/sherpa/cloud)
  --device, -d     GPU设备ID (0=自动检测)
  --no-stream      关闭流式识别
  --polish         开启AI润色
  --style          润色风格 (auto/formal/casual/technical)
```

## 技术栈

### 核心框架

| 技术 | 用途 |
|------|------|
| **FunASR / SenseVoiceSmall** | 语音识别引擎，支持中英日韩粤 |
| **PyTorch** | 推理后端，支持 CPU/CUDA |
| **pynput** | 全局热键监听 |
| **keyboard** | 键盘模拟打字 |
| **sounddevice** | 麦克风录音 |
| **soundfile** | WAV 音频读写 |
| **scipy** | 降噪信号处理 (STFT/ISTFT) |
| **numpy** | 音频数据处理 |
| **PyYAML** | 配置文件解析 |

### 架构设计

```
src/voice_input/
├── __main__.py          # 入口，终端UI + 事件循环
├── engine.py            # 核心状态机引擎 (IDLE→RECORDING→PROCESSING)
├── config.py            # 配置管理 (YAML + Dataclass)
├── protocols.py         # 接口协议定义
│
├── asr/                 # ASR 语音识别层（可插拔后端）
│   ├── base.py          # 抽象基类
│   ├── funasr_backend.py # FunASR/SenseVoice 后端 (默认)
│   ├── sherpa_backend.py # sherpa-onnx 后端
│   └── cloud_backend.py  # 云端API后端（预留）
│
├── audio/               # 音频处理层
│   ├── recorder.py      # 麦克风录音 + 增量音频获取
│   ├── vad.py           # 语音活动检测 (能量VAD + sherpa-onnx VAD)
│   └── noise_reducer.py # 频谱减法降噪
│
├── hotkey/              # 热键监听层
│   └── listener.py      # PTT/Toggle 热键 (pynput/keyboard)
│
├── output/              # 输出层
│   ├── clipboard.py     # 剪贴板输出 (pyperclip + Ctrl+V)
│   └── typer.py         # 键盘打字输出
│
├── text/                # 文本后处理
│   ├── processor.py     # 文本清理/规范化
│   ├── polisher.py      # AI润色 (Ollama/OpenAI)
│   └── hotwords.py      # 热词管理 & 纠正
│
└── gui/                 # GUI 层（预留）
    └── tray.py          # 系统托盘
```

## 功能特性

- **离线语音识别** — 无需联网，本地模型推理
- **流式识别** — 录音时实时显示识别文字，松开即输出
- **AI 文本润色** — 支持 Ollama/OpenAI 后端，多种风格
- **GPU 加速** — 自动检测 CUDA，支持指定 GPU 设备
- **智能降噪** — 频谱减法降噪，自动采集噪声样本
- **VAD 静音裁剪** — 录音后自动裁剪静音段，减少无效推理
- **多语言支持** — 中文/英文/日文/韩文/粤语
- **智能标点** — 自动添加标点符号
- **热词纠错** — 自定义热词映射表 (`hotwords.txt`)
- **双通道输出** — 剪贴板 + 键盘打字同时输出
- **中文路径兼容** — 自动处理含中文的 Windows 用户名路径

## 配置说明

编辑 `config.yaml` 自定义行为：

```yaml
audio:
  sample_rate: 16000
  silence_duration: 3.0       # 静音自动停止时间 (秒)
  max_duration: 60            # 最长录音时长 (秒)
  enable_noise_reduction: true # 开启降噪

asr:
  backend: "funasr"
  funasr:
    model: "d:/path/to/SenseVoiceSmall"  # 本地模型路径
    language: "zh"           # 语言: zh / en / ja / ko / auto
    device: "auto"           # auto / cpu / cuda:0
    enable_punctuation: true  # 自动添加标点

hotkey:
  ptt_key: "f9"              # 录音热键
  toggle_key: "alt_r"        # 切换模式热键
  mode: "ptt"                # ptt(按住说) / toggle(切换)

output:
  mode: "both"               # both / clipboard / typing

streaming:
  enabled: true              # 开启流式识别
  interval: 0.3              # 流式更新间隔 (秒)

polish:
  enabled: false             # 开启AI润色
  backend: "ollama"          # ollama / openai
  style: "auto"              # auto / formal / casual / technical
  ollama:
    model: "qwen2.5:0.5b"
    host: "http://localhost:11434"
```

## 开发过程与问题解决

### Day 1 — 项目骨架搭建
- 初始化项目结构、配置体系、状态机引擎
- 实现音频录制 (VAD)、全局热键 (PTT/Toggle)、双通道输出

### Day 2 — ASR 语音识别集成
- 集成 sherpa-onnx 后端（初始方案）
- 切换至 FunASR 后端（最终方案，兼容性更好）
- 修复热键重复触发、配置加载嵌套问题

### Day 3 — 体验优化与工程化
- 极简终端输出（隐藏噪音日志）
- 中文路径兼容性修复
- 完善 README 与开发文档

### Day 4 — 流式识别与AI润色
- 实现流式识别：录音时实时显示识别文字
- 集成 AI 润色模块：支持 Ollama 和 OpenAI 后端
- 多种润色风格：正式、随意、技术、自动

### Day 5 — 性能优化与GPU加速
- 流式识别延迟优化：1.0s → 0.3s 间隔
- 标点模型懒加载：启动时只加载主模型
- 频谱减法降噪：自动采集噪声样本，STFT 频域处理
- GPU 加速支持：自动检测 CUDA，配置设备参数
- VAD 静音裁剪：录音后自动裁剪静音段，减少无效推理
- 流式识别内存优化：增量音频获取，避免重复拼接和编码
- 静音检测阈值优化：1.5s → 3.0s，避免说话停顿误触

### 关键问题解决

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 启动无限等待 | sounddevice/scipy 提前导入 | 延迟导入，按需加载 |
| WAV 写入卡死 | scipy.io.wavfile 不支持 BytesIO | 改用 soundfile |
| 中文路径报错 | sentencepiece 不支持非 ASCII | 自动复制到临时目录 |
| 流式识别内存爆 | 每次全量拼接+降噪+WAV编码 | 增量PCM获取+手动WAV头构建 |
| 录音突然停止 | 静音检测1.5s太短 | 调整为3.0s |
| 文本输出到错误窗口 | keyboard.write() 不稳定 | 改用剪贴板+Ctrl+V |

## 故障排除

### Q1: 启动卡在"加载模型中"
FunASR 模型约 900MB，加载需要 10-20 秒，请耐心等待。用 `-v` 参数查看详细日志。

### Q2: 按 F9 没有反应
确认看到 `启动完成!` 提示后再操作。部分终端需要管理员权限。

### Q3: 识别结果不准确
- 确保麦克风权限已开启
- 调整 `silence_duration` 参数
- 开启降噪：`enable_noise_reduction: true`

### Q4: GPU 未被使用
需要安装 CUDA 版 PyTorch，CPU 版本无法使用 GPU。参见上方 GPU 加速章节。

### Q5: 中文路径报错
已自动处理，模型会被复制到临时目录。

## License

MIT License

## 致谢

- [FunASR / SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里达摩院语音识别模型
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) — Kaldi 团队 ONNX 推理引擎
- [ModelScope](https://www.modelscope.cn) — 魔搭社区模型托管
