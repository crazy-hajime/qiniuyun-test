# 📋 开发过程：PR 与 Commit 记录

> 开发周期：3 天 | 每日提交若干 commit | 按阶段推进

---

## 🗓️ Day 1 — 项目骨架搭建与音频采集

### 目标
搭建完整项目结构，实现麦克风录音、热键监听、基础状态机。

### Commit 1: `feat: 初始化项目结构与核心架构`

**文件**: `pyproject.toml`, `src/voice_input/__init__.py`, `protocols.py`, `config.py`, `engine.py`

**内容**:
- 创建 Python 包结构，`setuptools` 可编辑安装
- 定义 `ASRResult`、`ASRBase` 协议接口（策略模式）
- 实现 `AppConfig` 配置体系（Pydantic Dataclass + YAML）
- 实现 `VoiceEngine` 状态机引擎（IDLE → RECORDING → PROCESSING）
- 设计模块化目录：`asr/`, `audio/`, `hotkey/`, `output/`, `text/`, `gui/`

**设计决策**:
- 使用 **协议驱动** 设计，ASR 后端可插拔（FunASR / sherpa-onnx / 云端）
- 使用 **asyncio** 异步架构，避免阻塞 UI
- 配置文件优先级：命令行 > 项目 config.yaml > 用户目录 > 默认值

---

### Commit 2: `feat: 音频录制与语音活动检测 (VAD)`

**文件**: `src/voice_input/audio/recorder.py`, `audio/vad.py`

**内容**:
- 基于 `sounddevice` 实现麦克风录音（16kHz, 单声道, int16）
- 实现基于能量的 VAD（语音活动检测）：静音阈值检测、最长录音时长限制
- 录音数据以 bytes 返回，支持后续 ASR 处理

**技术细节**:
```python
# 录音参数
sample_rate = 16000    # 16kHz 采样率（ASR 标准采样率）
channels = 1           # 单声道
block_size = 1024      # 音频块大小
silence_threshold = 0.01  # 静音能量阈值
max_duration = 60       # 最长录音 60 秒
```

---

### Commit 3: `feat: 全局热键监听 (PTT/Toggle)`

**文件**: `src/voice_input/hotkey/listener.py`, `config.py`(HotkeyConfig)

**内容**:
- 基于 `pynput` 实现全局热键监听（不依赖窗口焦点）
- 支持 PTT（Push-To-Talk）模式：按住说话，松开识别
- 支持 Toggle 模式：按一下开始，再按一下结束
- 默认热键：F9（录音）、Alt+R（切换）

**遇到的问题 & 解决**:

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 热键重复触发 | pynput 的 `on_press` 在按住期间持续触发 | 添加 `_ptt_held` / `_toggle_fired` 状态锁，每个按键只触发一次 |

---

### Commit 4: `feat: 输出层 - 剪贴板与键盘打字`

**文件**: `src/voice_input/output/clipboard.py`, `output/typer.py`

**内容**:
- 剪贴板输出：基于 `pyperclip`，支持延迟写入避免冲突
- 键盘打字输出：基于 `keyboard` 库模拟逐字输入
- 双通道模式：可配置同时输出到剪贴板和键盘

---

## 🗓️ Day 2 — ASR 语音识别集成

### 目标
接入离线语音识别模型，完成"录音 → 识别 → 输出"全链路打通。

### Commit 5: `feat: sherpa-onnx 后端 (初始方案)`

**文件**: `src/voice_input/asr/sherpa_backend.py`

**内容**:
- 集成 `sherpa-onnx` 作为首选 ASR 后端
- 支持 SenseVoice / Paraformer 两种模型
- 自动从 GitHub / ModelScope / HuggingFace 下载模型
- 支持多语言：zh/en/ja/ko/yue/auto

**遇到的问题 & 解决**:

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 模型下载慢/失败 | GitHub 在国内访问不稳定 | 实现多镜像源自动切换（GitHub → ModelScope → HuggingFace） |
| 模型路径找不到 | 用户未配置 model_dir | 自动搜索缓存目录，找不到则提示下载 |

---

### Commit 6: `fix: 热键重复触发导致多次 start_recording`

**文件**: `src/voice_input/hotkey/listener.py`

**问题现象**: 按住 F9 时 `start_recording()` 被调用多次，导致状态异常

**根因分析**: `pynput.keyboard.Listener.on_press` 在按键按住期间会持续回调（约每 30ms 一次）

**解决方案**:
```python
self._ptt_held = False  # 状态锁

def on_press(key):
    if key == ptt_key and not self._ptt_held:  # 仅首次触发
        self._ptt_held = True
        self._on_ptt_press()

def on_release(key):
    if key == ptt_key:
        self._ptt_held = False  # 释放时重置
        self._on_ptt_release()
```

---

### Commit 7: `fix: 配置加载嵌套 Dataclass 转换失败`

**文件**: `src/voice_input/config.py`

**问题现象**: YAML 中 `asr.funasr.model` 无法正确映射到 `FunASRConfig.model`

**根因**: `_dict_to_dataclass` 未处理嵌套的 dataclass 字段，YAML 字典直接赋值给 dataclass 导致类型错误

**解决方案**: 递归检查字段是否为 dataclass，若是则递归转换：
```python
if hasattr(default_val, "__dataclass_fields__") and isinstance(value, dict):
    kwargs[name] = _dict_to_dataclass(type(default_val), value)
```

---

### Commit 8: `feat: FunASR 后端 (最终方案)` ⭐

**文件**: `src/voice_input/asr/funasr_backend.py`

**背景**: sherpa-onnx 在 Windows + Python 3.13 上存在致命 bug：
```
IndexError: invalid unordered_map<K, T> key
```
该错误在 sherpa-onnx 1.10~1.13 所有版本上均复现，是 onnxruntime 在 Windows 上的已知兼容性问题。

**决策**: 将默认后端从 `sherpa` 切换为 `funasr`（PyTorch 版本）

**实现要点**:
1. 使用 `funasr.AutoModel` 加载 SenseVoiceSmall 模型
2. 通过临时 wav 文件或 numpy 数组传递音频
3. 清理 SenseVoice 输出的特殊标签（`<\|zh\|><\|NEUTRAL\|>`）
4. 自动处理中文路径问题（sentencepiece 不支持中文用户名）

**遇到的问题 & 解决**:

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `IndexError: invalid unordered_map<K, T>` | sherpa-onnx + Windows 兼容性 bug | 切换到 FunASR PyTorch 后端 |
| `OSError: Not found: ...罗欣...bpe.model` | sentencepiece 不支持含中文字符的路径 | 自动检测并复制模型到纯英文路径 (`_get_safe_cache_dir()`) |
| `File-based transcription failed: [WinError 2]` | FunASR 尝试调用 ffmpeg 但不在 PATH | 改为优先用数组输入方式 |
| config.yaml 找不到 | 从非项目目录运行时无法定位配置 | `load_config` 增加多路径搜索（当前目录 + 源码目录） |

---

## 🗓️ Day 3 — 体验优化与工程化完善

### 目标
优化终端输出体验，完善工程化规范，确保开箱即用。

### Commit 9: `refactor: 极简终端输出`

**文件**: `src/voice_input/__main__.py`

**改造前**（日志杂乱）:
```
13:26:09 [INFO] __main__: 正在初始化语音引擎...
Notice: ffmpeg is not installed...
funasr version: 1.3.1.
[WARNING] root: trust_remote_code: False
rtf_avg: 0.330: 100%|███████| 1/1
识别结果: 这是一个语音输入法。
```

**改造后**（极简干净）:
```
这是一个语音输入法。🎤 ⠹ 录音中 ...
喂喂喂，能听到吗
```

**实现手段**:
- 初始化期间完全屏蔽 stdout/stderr（`_Silent` 类）
- 日志级别提升至 ERROR（只显示真正错误）
- 设置 `TQDM_DISABLE=1` 和 `MODELSCOPE_DISABLE_REMOTE=1` 环境变量
- 录音时显示旋转 spinner 动画（`⠋⠙⠹...`）
- 识别结果直接打印文字，无任何前缀

---

### Commit 10: `fix: 中文用户名路径兼容性`

**文件**: `src/voice_input/asr/funasr_backend.py`, `src/voice_input/config.py`

**问题**: 中国大陆 Windows 用户名常含中文（如 `C:\Users\罗欣\`），而 `sentencepiece` 库底层使用 C++，不支持非 ASCII 路径。

**解决方案**:
```python
def _get_safe_cache_dir() -> Path:
    home = Path.home()
    try:
        str(home).encode("ascii")  # 测试是否为纯英文
        return home / ".cache" / "voice-input" / "models"
    except UnicodeEncodeError:
        return Path(tempfile.gettempdir()) / "voice-input-models"
        # 回退到 C:\Users\xxx\AppData\Local\Temp\
```

---

### Commit 11: `docs: 完善 README 与快速启动文档`

**文件**: `README.md`, `pr和commit.md`

**内容**:
- GitHub 标准 README 结构（Badge / Demo / QuickStart / TechStack / Architecture）
- 一键安装脚本（pip install -e ".[funasr,hotkey]"）
- 架构图（ASCII tree）
- 功能特性清单
- 本文档（开发过程记录）

---

### Commit 12: `chore: pyproject.toml 依赖更新`

**文件**: `pyproject.toml`

**更新**:
- FunASR 依赖组：`funasr>=1.0.0, torch>=2.0.0, torchaudio, modelscope, soundfile`
- 默认后端改为 `funasr`
- 新增 `language` 配置项

---

## 🔑 关键技术决策记录

### 决策 1: 为什么选择 FunASR 而非 sherpa-onnx？

| 维度 | sherpa-onnx | FunASR (PyTorch) |
|------|------------|----------------|
| 模型格式 | ONNX | PyTorch (.pt) |
| 推理引擎 | onnxruntime | PyTorch |
| Windows 兼容性 | ❌ 存在 `unordered_map` bug | ✅ 正常工作 |
| 模型大小 | ~229MB (int8) | ~893MB (FP32) |
| 识别速度 | 快 | 稍慢但可接受 (RTF ~0.15) |
| 安装复杂度 | 低（单包） | 高（需 torch+torchaudio） |

**结论**: sherpa-onnx 更轻量但在 Windows 上存在致命兼容性问题，FunASR 更稳定可靠。

### 决策 2: 为什么用 PTT 模式而非 Toggle？

- PTT（Push-To-Talk）更符合直觉：按住说，松开停
- 避免误触发的尴尬（Toggle 模式容易忘记关闭）
- 减少不必要的录音时长

### 决策 3: 为什么选择 SenseVoice 模型？

- 多语言混合识别（中英日韩粤）
- 自带逆文本规范化（ITN）：`123` → `一百二十三`
- 自带标点恢复
- 情绪识别能力（可扩展）

---

## 📊 最终效果

```
┌─────────────────────────────────────┐
│  PS D:\qiniuyun\qiniuyun-test> voice-input --no-gui  │
│                                         │
│  这是一段测试语音。🎤 ⠹ 录音中 ...       │  ← 按住F9说话
│  这是一段测试语音。                      │  ← 松开后识别结果
│                                         │
│  你好世界。🎤 ⠸ 录音中 ...              │
│  你好世界。                              │
│                                         │
│  Ctrl+C 退出                             │
└─────────────────────────────────────┘
```

**功能验证通过**:
- ✅ 按住 F9 开始录音，spinner 动画旋转
- ✅ 松开 F9 自动识别，文字输出到光标处
- ✅ 文字同时复制到剪贴板
- ✅ 终端无冗余信息，极简输出

---

## 🗓️ Day 4 — AI 创新功能：流式识别 + AI润色

### 目标
将基础语音输入提升为智能语音助手体验，新增流式实时识别和 AI 文本润色。

### Commit 13: `feat: 新增流式识别和AI智能润色功能` ⭐

**PR**: #3 — `PR-streaming-polish.md`

**文件**: `config.yaml`, `src/voice_input/__main__.py`, `audio/recorder.py`, `config.py`, `engine.py`, `text/__init__.py`, `text/polisher.py`(新建)

### 功能 1: 流式实时识别 (Streaming ASR)

**实现方案**:
```python
# engine.py 新增流式识别定时器
def _do_partial_transcribe(self):
    with self._stream_lock:  # 线程安全
        audio_data = self._recorder.get_audio_data()
        partial_text = asyncio.run(self._async_recognize(audio_data))
        if partial_text != self._last_partial_text:
            self._on_partial(processed)
```

**核心改动**:
- `engine.py`: 新增 `threading.Timer` 定时器，每1秒增量识别
- `recorder.py`: 修复 `get_audio_data()` 条件判断反了（录音中返回空）
- `engine.py`: 新增 `threading.Lock` 防止重叠 ASR 调用
- `__main__.py`: 新增 `on_partial` 回调，实时展示中间结果

**效果对比**:

| 之前 | 之后 |
|------|------|
| 说完→等待→一次性出字 | 边说边出字，感觉更实时 |
| `🎤 ⠹ 录音中 ...` | `🎤 ⠿ 今天天气真不错` |

### 功能 2: AI智能润色 (AI Text Polish)

**新增文件**: `src/voice_input/text/polisher.py`

**架构设计**:
```
ASR识别 → TextProcessor → AIPolisher(可选) → Output
                                │
                     ┌──────────┼──────────┐
                     ▼          ▼          ▼
                  Ollama      OpenAI     (可扩展)
```

**双后端支持**:

| 后端 | 协议 | 优势 | 配置 |
|------|------|------|------|
| Ollama | `/api/generate` | 本地离线、隐私安全、免费 | `ollama pull qwen2.5:0.5b` |
| OpenAI | `/chat/completions` | 云端高质量 | `config.yaml` 填入 api_key |

**四种润色风格**:
```python
STYLE_PROMPTS = {
    "auto": "修正错别字和语法错误，去除口语冗余词...",
    "formal": "改写为正式书面语...",
    "casual": "改写为轻松随意的口语风格...",
    "technical": "改写为技术文档风格...",
}
```

**遇到的问题 & 解决**:

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `get_audio_data()` 一直返回空 | 条件 `if self._is_recording: return b""` 写反了 | 去掉条件判断，直接返回缓冲区 |
| 流式识别和最终识别可能重叠调用 | Timer 线程和主线程同时调用 ASR | 添加 `threading.Lock` 非阻塞获取 |
| 配置文件新字段无法加载 | `_dict_to_dataclass` 假设用户配置覆盖所有字段 | 已有默认值机制，无需额外处理 |

**新增 CLI 参数**:
```bash
--no-stream        # 关闭流式识别
--polish           # 开启AI润色
--style {auto|formal|casual|technical}  # 润色风格
```

**新增配置段** (`config.yaml`):
```yaml
polish:
  enabled: false
  backend: "ollama"
  ollama:
    model: "qwen2.5:0.5b"
    host: "http://localhost:11434"
  openai:
    model: "gpt-3.5-turbo"
    api_key: ""
    base_url: "https://api.openai.com/v1"
  style: "auto"

streaming:
  enabled: true
  interval: 1.0
  show_partial: true
```

---

## 🔑 技术决策记录（续）

### 决策 4: 流式识别为何用定时器而非真正的流式 ASR？

SenseVoice 模型的 FunASR 封装不支持真正的 incremental streaming。替代方案：
1. **定时增量识别**: 每 N 秒对已录制的完整音频做 ASR（✅ 采用）
2. **WebSocket 流式 ASR**: 需额外部署服务，不适合离线场景
3. **VAD 分段**: 按静音自动切分并逐段识别

定时增量方案简单可靠，1 秒间隔足以给用户"实时"的感觉。

### 决策 5: AI润色为何默认关闭？

| 因素 | 考虑 |
|------|------|
| 隐私 | 云端 API 会发送文本，用户需知情同意 |
| 速度 | LLM 推理增加 1-3 秒延迟 |
| 依赖 | Ollama 需额外安装 |
| 准确性 | LLM 可能改变用户原意 |

因此润色功能需用户主动 `--polish` 开启，不会在后台偷偷调用。

### 决策 6: 为什么用 Ollama 作为默认润色后端？

- **完全离线**: 无需网络，数据不出本地
- **一键安装**: `ollama pull qwen2.5:0.5b` 即可
- **速度可控**: 0.5B 小模型推理 < 1 秒
- **免费**: 无 API 费用
