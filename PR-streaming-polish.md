# 🚀 Feat: 流式识别 + AI智能润色

> **PR 类型**: Feature  
> **优先级**: ⭐ High  
> **影响范围**: 核心引擎 + 终端UI + 配置系统  
> **测试状态**: ✅ 语法/导入通过

---

## 功能概述

本次 PR 新增两大核心能力，将基础语音输入提升为智能语音助手级体验。

### 🎯 功能 1: 流式实时识别 (Streaming ASR)

**之前**: 按住 F9 说完话 → 松开 → 等待 → 一次性出字  
**现在**: 按住 F9 说话 → **边说边出字** → 松开 → 最终确认

**技术实现**:
- `engine.py`: 新增 `threading.Timer` 定时器，每 1 秒触发增量 ASR
- 非破坏性读取录音缓冲区 (`get_audio_data()`)
- `threading.Lock` 线程安全锁防止重叠 ASR 调用
- 去重逻辑：仅当文本变化时才推送更新

**效果演示**:
```
  🎤 ⠿ 今天天气        ← 第1秒
  🎤 ⠿ 今天天气真不错   ← 第2秒  
  ✅ 今天天气真不错，适合出去玩  ← 松开F9，最终结果
```

---

### 🎯 功能 2: AI智能润色 (AI Text Polish)

**新增 `text/polisher.py` 模块**，识别完成后自动调用 LLM 润色文本。

**双后端支持**:

| 后端 | 适用场景 | 配置 |
|------|---------|------|
| **Ollama** (默认) | 本地离线，隐私安全 | `ollama pull qwen2.5:0.5b` |
| **OpenAI** | 云端高质量，需API Key | `config.yaml` 填入 key |

**四种润色风格**:

| 风格 | 说明 | 示例 |
|------|------|------|
| `auto` | 自动修正口语/错字 | "那个那个我觉得" → "我觉得" |
| `formal` | 正式书面语 | "这玩意挺好的" → "该方案质量优秀" |
| `casual` | 轻松口语风 | "会议延期到明天" → "会议改明天啦～" |
| `technical` | 技术文档风格 | "修了个bug" → "修复了一处程序缺陷" |

**效果演示**:
```
  🎤 ⠿ 那个那个就是说我觉得这个方案是可以的
  ✅ 我觉得这个方案是可以的        ← ASR原文
  ✨ 我认为该方案是可行的          ← AI润色后
```

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/voice_input/text/polisher.py` | **新建** | AI润色核心模块 (Ollama + OpenAI) |
| `src/voice_input/config.py` | 修改 | +PolishConfig/StreamingConfig/OllamaConfig/OpenAIConfig |
| `src/voice_input/engine.py` | 修改 | +流式定时器/+润色集成/+线程安全锁 |
| `src/voice_input/__main__.py` | 修改 | +CLI参数/流式展示/润色展示 |
| `src/voice_input/audio/recorder.py` | 修复 | get_audio_data() 条件反了 |
| `src/voice_input/text/__init__.py` | 修改 | 导出 AIPolisher |
| `config.yaml` | 修改 | +polish/+streaming 配置段 |

```
 config.yaml                 |  17 +++++
 src/voice_input/__main__.py |  41 ++++++++-
 src/voice_input/audio/recorder.py |   2 -
 src/voice_input/config.py   |  31 +++++++
 src/voice_input/engine.py   |  92 +++++++++++++++++--
 src/voice_input/text/__init__.py |   3 +-
 src/voice_input/text/polisher.py | 144 ++++++++++++++++++++++++++ (new)
 ─────────────────────────────────────────────────────
 7 files changed, 320 insertions(+), 13 deletions(-)
```

---

## 使用方式

```bash
# 默认（流式识别开启）
python -m voice_input

# 关闭流式
python -m voice_input --no-stream

# 开启AI润色（需先安装Ollama）
python -m voice_input --polish

# AI润色 + 正式风格
python -m voice_input --polish --style formal

# 全部开启
python -m voice_input --polish --style auto
```

**安装 Ollama (润色前置条件)**:
```bash
# 1. https://ollama.com 下载安装
# 2. 拉取模型
ollama pull qwen2.5:0.5b
```

---

## 配置参考

```yaml
# config.yaml 新增配置段
polish:
  enabled: false          # 默认关闭，--polish 开启
  backend: "ollama"       # ollama | openai
  ollama:
    model: "qwen2.5:0.5b" # 推荐小模型，速度快
    host: "http://localhost:11434"
  openai:
    model: "gpt-3.5-turbo"
    api_key: ""
    base_url: "https://api.openai.com/v1"
  style: "auto"           # auto | formal | casual | technical

streaming:
  enabled: true           # 默认开启
  interval: 1.0           # 增量识别间隔(秒)
  show_partial: true      # 显示中间结果
```

---

## 后续计划

- [ ] 流式识别性能优化（减少 ASR 调用频率）
- [ ] 支持更多本地 LLM 后端（llama.cpp）
- [ ] AI润色缓存（相同输入不重复润色）
- [ ] 语音指令系统（"删除上一句""换行"等）