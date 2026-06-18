---
name: development-history
description: 开发历程、真机验证结果、重要 bug 复盘、技术演化轨迹
metadata:
  type: project
---

# 开发历程

更新时间：2026-06-17

---

## 项目起源

**原始背景：** 2026 中兴捧月初赛 - 移动端 GUI Agent 赛道

**转型时刻：** 2026-05-21，用户明确："现在我不是在打比赛了，可以完全自由发挥做产品。"

**Why：** 比赛 BaseAgent 有签名验证、强制 disabled thinking、固定 model 等约束，对产品是束缚；比赛文件提交时会被替换，共享代码反而是隐患。

**结果：** 从零构建 `seetouch/` 产品包，与比赛代码完全独立，互不 import。

---

## 技术选型决策（2026-05-12）

| 项 | 选择 | 不选的原因 |
|---|---|---|
| 设备控制层 | uiautomator2 | 纯 ADB+ADBKeyboard 中文输入门槛高；Appium 配置重、启动慢 |
| 代码复用 | **从零写，不 import 比赛代码** | BaseAgent 强约束太多；参考 prompt/解析逻辑即可 |
| 执行模式 | 自动连续 + 敏感动作前确认 | 全自动有真实风险，每步确认极慢 |
| 坐标体系 | 0-1000 归一化（沿用比赛） | 模型已习惯；perception 层负责像素换算 |
| OPEN 启动策略 | 静态表 + 多级 fallback | 用户接受静态表但要求兜底，不要硬编码全量 |
| Doubao thinking | 默认 `auto`（不再强制 disabled） | 比赛规则不再约束，模型按需启动 VisualCoT |

---

## 里程碑事件

### 2026-05-21：产品包首次提交

- **commit**: `ccce867` (40 文件 / +2887 行)
- **核心模块**: core / device / perception / reasoning / safety / cli
- **测试覆盖**: 40 单元测试全绿
- **真机验证**: Xiaomi rubens / Android 12 / 1440×3200 / 447 包

**首次真机测试结果：**

| 任务 | 步数 | 时长 | tokens(in/out) | 结果 |
|---|---|---|---|---|
| 打开抖音 | 2 | 11s | 5145/165 | ✓ L2 直通 |
| 在哔哩哔哩搜索采莲曲 | 6 | 27s | 16468/458 | ✓ 完整闭环（含中文输入） |

**验证点：**
- OPEN/CLICK/TYPE(中文)/COMPLETE 四个动作端到端通
- Prompt 里 screen_summary 链路在真机上正确延续
- B 站任务路径：OPEN → CLICK 搜索框 → TYPE "采莲曲" → CLICK 搜索按钮 → COMPLETE

---

### 2026-05-21：启用 Doubao thinking

- **commit**: `73a9e41`
- **默认**: `auto` 模式（模型按需 VisualCoT）
- **配置**: `SEETOUCH_THINKING_MODE` 环境变量
- **成本监控**: `_extract_usage` 带 `reasoning_tokens`

---

### 2026-06-01：WAIT 协议 + 移除 fuzzy 匹配

- **commit**: `dde04ba` (+293 行 / -167 行)
- **核心变更**:
  - 新增 WAIT 动作（0.5-5 秒）
  - 移除 fuzzy_match 整段代码
  - 视觉兜底命中检测（前台切换时自动学习）
  - thinking 模式默认改 `enabled`（vision 模型不支持 auto）

**测试覆盖**: 42 单元测试（从 40 → 42）

---

### 2026-06-17：提取为独立仓库

- **仓库路径**: `D:\科研\phone-agent`
- **默认分支**: `main`
- **保留历史**: 3 个产品相关 commit（ccce867 / 73a9e41 / dde04ba）
- **目录结构**: `seetouch/` 提到根目录

---

## 重大 bug 复盘

### 首次真机死循环（2026-05-20）

**症状：** "打开抖音" 连续 12+ 步重复 OPEN，直到用户打断。

**根因链：**
1. 模型输出 `com.zhiliaoapp.musically`（TikTok 海外版，非国内抖音）
2. 设备未安装，L3 fuzzy_match 在 447 个包里误匹配到 `com.biquge.ebook.app`（笔趣阁）
   - `com.` 公共前缀让相似度虚高
   - `app` 末尾段 3 字符未被黑名单化
3. `_learn` 立即把错误结果写入 cache，后续重试始终用错的
4. 模型识别出"这是笔趣阁不是抖音"，再次 OPEN，Runner 无死循环检测 → 无止境

**修复措施（全部已上线）：**
- **移除 fuzzy_match**（从 L3 直接跳 L4 视觉兜底）
- PACKAGE_ALIASES 表（TikTok → 抖音等）
- verify-then-learn（启动后轮询 `current_app()`，通过才写 cache）
- Runner 加 `consecutive_identical_actions=3`，3 步同动作即 abort
- Prompt 强调"必须用国内大陆版 package"

**经验：**
- fuzzy match 在 Android 包名场景假阳性极高，不适用
- learned cache 永远不要在执行前写入，只能事后基于结果回写
- 死循环检测是产品必须，不能依赖人工监控

详见 [[technical_decisions.md]]

---

### WAIT 协议缺失（2026-05-31）

**症状：** "在哔哩哔哩搜索采莲曲"，B 站启动后模型输出 `{"action": "WAIT"}`，parser 失败兜底返回 `Action(COMPLETE)`，任务被"假完成"提前终止。

**修复：**
- Action 新增 `ACTION_WAIT`，参数 `{"seconds": float}` 可选
- parser 失败的 fallback 从 COMPLETE 改成 WAIT
- Prompt 加 WAIT 用法说明

**经验：** 静默 fallback 到 COMPLETE 极其危险——任何 parser bug 都会被伪装成"任务完成"。模型有合理需求时优先**加协议**，不要用兜底掩盖问题。

---

### thinking_mode=auto 不支持（2026-05-31）

**症状：** API 报 400：`Unsupported thinking type for the current model: auto`

**根因：** doubao-seed-1-6-vision-250815 只支持 `enabled` / `disabled`，vision 模型的 thinking 模式集合比文本模型小。

**修复：** 默认改 `enabled`（准确率优先）

**经验：** 添加新模型时先用 `extra_body={"thinking": {"type": "..."}}` 探测支持的模式集合。

---

## 真机测试数据

### 设备环境
- **型号**: Xiaomi rubens（MIUI）
- **系统**: Android 12 / SDK 31
- **分辨率**: 1440×3200
- **已装应用**: 447 个包
- **静态表命中率**: 17/34（B 站、抖音、微信、QQ、小红书、淘宝、京东、拼多多、美团、高德、百度地图、去哪儿、支付宝、夸克等）

### thinking=enabled 性能（2026-05-31）

| 任务 | 步数 | 时长 | tokens(in/out) | 结果 |
|---|---|---|---|---|
| 打开抖音 | 2 | 102s | 5565/297 | ✓ L2 直通 |
| 在哔哩哔哩搜索采莲曲 | 9 | 67s | 28409/1705 | ✓（发现 WAIT bug，修复后通过） |

**观察：**
- 步均 7-12s，比 disabled 慢 2-3 倍
- 识别准确率明显提高（B 站开屏广告自动跳过、复杂搜索场景不再瞎点）
- B 站任务有 step 重复（4-5 重复点搜索框，7-8 重复点搜索按钮）—— 模型保险性重复，任务能完成但低效

**优化方向：** Prompt 可加"刚才点过的位置不用再点，等待页面响应，不响应再 WAIT"。

---

## 视觉兜底演化（三轮迭代）

测试对象：**李跳跳**（`cn.litiaotiao.app`，无障碍跳广告工具），装了但桌面没直接图标——被放在桌面第一页"系统工具"文件夹里。

### Iteration 1：无 prompt 引导
- **现象**: step 1 OPEN 失败 → step 2/3 继续 OPEN 同名 app → 死循环
- **根因**: Runner 加的 note 只是 `open_app_visual_fallback: 李跳跳`，模型不知道要换 CLICK

### Iteration 2：note + prompt 加硬规则
- **note 激进措辞**: "❗ OPEN 'xxx' 失败，本步绝对不要再 OPEN 同名 app，必须 CLICK 桌面图标"
- **prompt 硬规则**: 历史里看到 `OPEN '<app>' 失败` 字样，本步绝对不能再 OPEN
- **效果**: 不再死循环，正确 SCROLL 翻页 + 上滑抽屉，但翻 8 页找不到（因为在文件夹里）

### Iteration 3：桌面文件夹支持（待真机验证）
- **识别**: 图标内 4/9 个 app 预览 + 外框 + 分组名
- **展开**: CLICK 文件夹中心
- **退出**: CLICK 屏幕底部空白（如 `[500,950]`）
- **放弃条件**: 翻完所有页 + 探索过名字相关的文件夹 + 抽屉滚到底

**经验：** 桌面文件夹是 Android 设备非常普遍的 UI 元素，产品 prompt 不能假设 app 一定有顶层图标。

---

## MIUI 踩坑（已知问题，无需修复）

1. **`python -m uiautomator2 init` 末尾会报 ADBKeyboard.apk 安装失败** —— MIUI 默认拦截 USB 安装来源不明应用。**这不影响主流程**：产品的中文输入用 `d(focused=True).set_text()` 走原生 UIAutomator，不依赖 ADBKeyboard IME。出现 `Failure Unknown` 直接忽略。

2. **手机端开发者选项至少要开**：USB 调试、USB 调试(安全设置)、USB 安装。

3. u2 主服务装好的标志是 `[server] INFO: http server listening on *:9008`。

---

## 相关记忆

- [[technical_decisions.md]] — fuzzy 匹配移除详细原因、WAIT 协议设计
- [[product_overview.md]] — 产品定位、核心能力
- [[future_roadmap.md]] — 下一步计划、on-device APP 迁移路径
