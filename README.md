# SeeTouch

<div align="center">

**Vision-driven mobile GUI agent that sees your screen and operates your phone via natural language.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-42%20passing-brightgreen.svg)](#测试)

[English](README_EN.md) | 简体中文

</div>

---

## 简介

SeeTouch 是一个基于视觉语言模型（VLM）的 Android GUI 自动化工具，能够理解屏幕内容并将自然语言指令转换为手机操作序列。

### 核心特性

- **自然语言控制** — 用中文描述任务，自动完成跨应用操作
- **视觉理解** — 基于 Doubao Vision 模型识别控件、文本、广告等复杂场景  
- **智能启动** — 五级 fallback 策略自动适配中文 app 名称  
- **安全防护** — 支付、下单等敏感操作自动拦截并请求确认  
- **模块化架构** — 设备层抽象支持扩展到 Web、桌面等平台

### 典型场景

```bash
python -m seetouch run "打开抖音"
python -m seetouch run "在哔哩哔哩搜索采莲曲"
python -m seetouch run "打开抖音我的喜欢里搜索跳舞的视频"
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Android 设备（开启 USB 调试）或模拟器
- ADB 工具
- 火山引擎 API Key（或其他支持的 VLM 服务）

### 安装

```bash
git clone https://github.com/YidaYang/seetouch.git
cd seetouch
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -e .
```

### 配置 Android 设备

1. **连接设备**  
   USB 连接手机或配置无线 ADB：
   ```bash
   adb devices
   ```
   应能看到你的设备列表。

2. **初始化 uiautomator2**  
   自动在手机上安装 atx-agent 服务：
   ```bash
   python -m uiautomator2 init
   ```
   > **注意（MIUI 用户）**：末尾可能报 ADBKeyboard.apk 安装失败，但不影响主流程（产品使用原生 UIAutomator API 输入中文）。

3. **开发者选项**  
   确保已开启：USB 调试 / USB 调试(安全设置) / USB 安装

### 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：
```ini
VLM_API_KEY=你的火山方舟_API_Key
DOUBAO_MODEL_ID=doubao-seed-1-6-vision-250815
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3

# 可选配置
SEETOUCH_DEVICE_SERIAL=       # 多设备时指定
SEETOUCH_MAX_STEPS=45         # 单任务最大步数
SEETOUCH_THINKING_MODE=enabled # enabled|disabled
```

### 自检

运行诊断脚本检查环境：
```bash
python -m seetouch.scripts.doctor
```

### 运行任务

```bash
python -m seetouch run "打开抖音"
```

任务执行过程中：
- 自动截图、推理、执行动作
- 敏感操作（支付、下单、发送消息）会暂停请求确认
- 结果保存到 `./runs/<timestamp>/` 目录

### 调试器

图形化调试器支持实时截图显示、单步执行、prompt/模型输出查看：

```bash
# 安装调试器依赖
pip install -e ".[debugger]"

# 启动调试器（浏览器自动打开）
python -m seetouch debug
python -m seetouch debug --port 8080   # 指定端口
```

调试器功能：
- 📱 **实时截图** — CLICK 标注红点+十字准星，SCROLL 标注轨迹箭头
- 📝 **完整信息** — Action、Screen Summary、Prompt（可折叠）、Model Output（可折叠）、Token 用量
- ⏭ **单步执行** — 逐步观察每一步的截图、推理、动作
- ▶ **连续运行** — 自动执行，支持随时暂停
- 🕐 **历史回看** — 底部时间线可点击查看任意历史步骤

---

## 架构设计

### 目录结构

```
seetouch/
├── core/           # 主循环、Action、Task、Session
│   ├── action.py   # 动作协议（CLICK/TYPE/SCROLL/OPEN/WAIT/COMPLETE）
│   ├── runner.py   # 状态机执行器（start/step/run）
│   ├── task.py     # 任务定义
│   └── session.py  # 会话管理 + StepResult 数据类
├── device/         # 设备控制层
│   ├── base.py     # DeviceController 抽象接口
│   └── android/    # uiautomator2 实现
├── perception/     # 视觉处理
│   ├── screen.py   # 坐标转换（0-1000 归一化）
│   └── image.py    # 图像编码
├── reasoning/      # 推理层
│   ├── base.py     # Reasoner 抽象接口
│   ├── doubao.py   # Doubao Vision 实现
│   └── prompts/    # Prompt 模板
├── safety/         # 安全防护
│   └── guard.py    # 敏感动作识别
├── debugger/       # 图形化调试器
│   ├── app.py      # Flask + SocketIO 服务
│   ├── debug_session.py  # 调试会话管理
│   └── static/     # Web UI（HTML/CSS/JS）
├── cli/            # 命令行入口
└── scripts/        # 工具脚本
    └── doctor.py   # 环境诊断
```

### 核心概念

#### 动作协议

| 动作 | 参数 | 说明 |
|------|------|------|
| `CLICK` | `{"point": [x, y]}` | 点击控件（坐标 0-1000） |
| `TYPE` | `{"text": "..."}` | 输入文本（支持中文） |
| `SCROLL` | `{"start_point": [x,y], "end_point": [x,y]}` | 滑动 |
| `OPEN` | `{"app_name": "抖音"}` | 启动应用 |
| `WAIT` | `{"seconds": 1.5}` | 等待加载（0.5-5 秒） |
| `COMPLETE` | `{}` | 任务完成 |

#### OPEN 启动策略

五级 fallback 自动适配各种场景：

```
① learned cache  — 视觉学习到的中文名→包名映射
② L1 静态表      — 17 个高频 app（抖音、B站、微信等）
③ L1' alias      — 海外替代（TikTok→抖音）
④ L2 直通        — 直接使用包名
⑤ L4 视觉兜底    — 回桌面，视觉识别图标点击
```

> 视觉兜底成功后自动学习映射，持久化到 `~/.seetouch/learned_apps.json`

---

## 开发

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
# 全部测试（42 个单元测试）
pytest tests/

# 单个模块
pytest tests/test_parser.py -v

# 覆盖率报告
pytest --cov=seetouch --cov-report=html
```

### 代码规范

项目使用 Ruff 进行代码检查：
```bash
ruff check seetouch/
ruff format seetouch/
```

---

## 真机验证

**测试设备**: Xiaomi rubens / Android 12 / 1440×3200 / 447 已装应用

| 任务 | 步数 | 耗时 | 结果 |
|------|------|------|------|
| 打开抖音 | 2 | 11s | ✓ |
| 在哔哩哔哩搜索采莲曲 | 6 | 27s | ✓ |
| 视觉兜底（桌面文件夹内 app） | 8 | ~45s | ✓ |

---

## 性能与成本

### thinking_mode 对比

| 模式 | 步均耗时 | 准确率 | 适用场景 |
|------|---------|--------|---------|
| `disabled` | 3-5s | 中 | 简单任务、成本敏感 |
| `enabled` | 7-12s | 高 | 复杂场景（广告识别、小控件定位） |

> 默认 `enabled`（准确率优先），可通过 `SEETOUCH_THINKING_MODE` 环境变量调整

---

## 路线图

### 已完成 ✓
- [x] uiautomator2 设备控制层
- [x] Doubao Vision 推理引擎
- [x] 五级 OPEN 启动策略 + 视觉兜底
- [x] 敏感动作拦截
- [x] 死循环检测（连续 3 步相同动作自动中止）
- [x] 真机闭环验证（Xiaomi / MIUI）
- [x] 图形化调试器（Web UI + 单步执行 + 实时截图标注）

### 进行中 🚧
- [ ] 更多 VLM 后端支持（Claude、GPT-4V、本地模型）
- [ ] 多设备并行执行

### 未来计划 💡
- [ ] **on-device Android APP** — 独立运行在手机上，不依赖 PC
  - 使用 Android Accessibility Service 替代 uiautomator2
  - 端侧模型推理或云端 API
- [ ] 跨平台扩展（Web 自动化、桌面 GUI）
- [ ] 任务编排 DSL（定义多步工作流）

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

### 快速贡献流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'feat: add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

---

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源协议。

---

## 致谢

- [uiautomator2](https://github.com/openatx/uiautomator2) — Android 自动化核心
- [Doubao Vision](https://www.volcengine.com/docs/82379/1298454) — 视觉理解引擎

---

## 联系方式

- **Issues**: [GitHub Issues](https://github.com/YidaYang/seetouch/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YidaYang/seetouch/discussions)

---

<div align="center">

**如果本项目对你有帮助，请给一个 ⭐️ Star 支持！**

</div>
