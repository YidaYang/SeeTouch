---
name: product-overview
description: SeeTouch 产品定位、技术架构、核心能力概览
metadata:
  type: project
---

# SeeTouch 产品概览

更新时间：2026-06-19

---

## 产品定位

**SeeTouch 是一个 Android 真机 GUI Agent 产品**，通过 Vision-Language Model 理解屏幕内容，将自然语言指令转换为手机操作序列。

**核心价值：**
- 自然语言控制手机，无需学习复杂操作流程
- 跨应用任务自动化（搜索、下单、评论、设置等）
- 桌面级 GUI 理解能力（识别控件、文件夹、广告等复杂场景）

**典型场景：**
- "在哔哩哔哩搜索采莲曲"
- "打开抖音我的喜欢里搜索跳舞的视频"
- "去美团外卖购买窑村干锅猪蹄店的干锅排骨"

---

## 产品形态演化

**当前阶段（2026-06-17）：PoC 原型**
- PC 端 Python 程序 + uiautomator2 + ADB 控制真机
- 用于快速验证 reasoning / OPEN / 动作闭环核心逻辑
- 已跑通真机基础场景（打开 app、搜索、中文输入、完成任务）

**最终目标（已明确）：on-device Android APP**
- 独立运行在手机上，不依赖电脑
- 使用 Android 原生 API（PackageManager、Accessibility、截图、手势注入）
- 当前 PoC 阶段在手机端部署的任何 helper 组件，都按"将来要长进主 App"的标准设计

**Why：** 产品需要独立性和便携性，PC 端控制只是验证阶段的权宜之计。

**How to apply：** 写 Android 原生代码是产品主线方向，不是绕路。架构设计时保持设备层抽象（`device/base.py` Protocol），方便后续从 uiautomator2 迁移到 Accessibility Service。

---

## 技术架构

采用模块化分层设计，核心模块：

### core/
- `Action` — 动作协议（CLICK/TYPE/SCROLL/OPEN/WAIT/COMPLETE）
- `Task` — 任务定义（指令、状态、历史）
- `Session` — 单次运行会话（记录每步、生成报告）
- `Runner` — 主控循环（截图 → 推理 → 执行 → 记录）

### device/
- `DeviceController` Protocol（抽象接口）
- `AndroidController` 实现（基于 uiautomator2）
- 支持：截图、点击、输入、滑动、启动 app、查询前台 app

**扩展点：** `device/web/`、`device/desktop/` 未来可支持 Web 自动化、桌面 GUI

### reasoning/
- `Reasoner` Protocol（抽象接口）
- `DoubaoReasoner` 实现（火山引擎 Doubao-Seed-1.6-Vision）
- 模型配置：thinking_mode（enabled/disabled/auto）、temperature、max_tokens

**扩展点：** `openai.py`、`claude.py`、`local.py` 可接入其他多模态模型

### perception/
- 坐标转换（归一化 0-1000 ↔ 像素）
- 图像编码（PIL Image → base64 data URL）

### safety/
- 敏感动作识别（下单、支付、删除、分享等）
- 用户确认机制（敏感动作前暂停等待人工批准）

### cli/
- 命令行入口：`python -m seetouch run "指令"`
- 配置加载（环境变量 + `.env` 文件）

---

## 核心能力

### 1. 多模态视觉理解
- 使用 Doubao-Seed-1.6-Vision（支持 VisualCoT 视觉思维链）
- 识别控件位置、文本内容、应用状态、广告/弹窗等
- 输出归一化坐标（0-1000）+ 动作决策

### 2. OPEN 启动策略（五级 fallback）
```
① learned cache   — 视觉兜底学到的映射（持久化到 ~/.seetouch/learned_apps.json）
② L1 静态表       — 高频中文名 → package（17 个国民应用）
③ L1' alias       — 海外/旧版 package → 国内替代（TikTok → 抖音等）
④ L2 直通         — 输入本身是 package 格式且已安装
⑤ L4 视觉兜底     — 回桌面 + raise OpenAppNeedsVisual，交给 Runner 视觉识别图标点击
```

**关键设计：**
- 不维护全量映射表（用户反对硬编码）
- **移除 fuzzy 模糊匹配**（2026-05-21 起）—— Android 包名公共部分过多，假阳性高
- 视觉兜底自动学习：Runner 监测前台切换，首次进入非桌面 app 时回写 cache

参考：[[technical_decisions.md]]

### 3. 动作协议
- `CLICK {"point": [x, y]}` — 点击控件
- `TYPE {"text": "..."}` — 输入文本（支持中文）
- `SCROLL {"start_point": [x, y], "end_point": [x, y]}` — 滑动
- `OPEN {"app_name": "..."}` — 启动应用（中文名或 package）
- `BACK {}` — 系统返回键，回上一层 / 关弹窗（进错页面、误入子页面、重开流程时用）
- `WAIT {}` 或 `{"seconds": 1.5}` — 等待界面加载/动画/弹窗消失（0.5-5 秒）
- `COMPLETE {}` — 任务完成

### 4. 上下文管理
- 每步生成 `screen_summary` 和 `action_summary`
- 历史摘要传入下一步 prompt，避免重复截图 token 开销
- 死循环检测：连续 3 步相同动作自动中止

### 5. 真机验证通过场景
- 打开抖音（2 步 / 11s）
- 在哔哩哔哩搜索采莲曲（6 步 / 27s，含中文输入）
- 视觉兜底场景（桌面文件夹内 app 识别）

---

## 关键里程碑

| 日期 | 事件 | commit |
|---|---|---|
| 2026-05-21 | 产品包首次提交，真机闭环跑通 | ccce867 |
| 2026-05-21 | 启用 Doubao thinking，默认 auto 模式 | 73a9e41 |
| 2026-06-01 | WAIT 协议 + 移除 fuzzy 匹配 + 视觉兜底增强 | dde04ba |
| 2026-06-17 | 提取为独立仓库，main 分支 | - |
| 2026-06-19 | 全局重命名 Phone Agent → SeeTouch，准备开源 | e7e8cbe |
| 2026-06-19 | 正式开源发布到 GitHub（Apache 2.0） | a18bf7a |
| 2026-06-19 | 图形化调试器（Runner 状态机重构 + Web UI） | fc5c0e5 |

---

## 测试覆盖

- 42 单元测试（parser、screen、app_launcher、guard、runner-with-mock）
- 真机集成测试（Xiaomi rubens / Android 12 / 1440×3200 / 447 包）
- 覆盖场景：OPEN 五级 fallback、视觉学习、死循环检测、敏感动作拦截

---

## 相关记忆

- [[technical_decisions.md]] — OPEN 启动策略详细设计、fuzzy 匹配移除原因
- [[development_history.md]] — 真机死循环 bug 复盘、MIUI 踩坑、thinking 模式演化
- [[collaboration_style.md]] — 模块化优先、敏感操作先确认、bug 做根因分析
- [[future_roadmap.md]] — 最终 on-device APP 实现路径、helper APK 计划
