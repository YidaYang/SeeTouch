---
name: future-roadmap
description: 产品路线图、待解决问题、扩展方向、on-device APP 迁移计划
metadata:
  type: project
---

# 产品路线图

更新时间：2026-06-17

---

## 最终目标形态

**on-device Android APP** — 独立运行在手机上，不依赖电脑的原生 Android 应用。

**Why：** 产品需要独立性和便携性，PC 端控制只是验证阶段的权宜之计。

**当前状态：** PoC 原型（PC + uiautomator2 + ADB），用于快速验证 reasoning / OPEN / 动作闭环核心逻辑。

**How to apply：** 写 Android 原生代码（PackageManager、Accessibility、截图、手势注入）是产品主线方向，不是绕路。PoC 阶段在手机端部署的任何 helper 组件，都按"将来要长进主 App"的标准设计。

---

## 近期待办

### 1. 应用名解析方案（已确定，待实现）

**目标：** 彻底解决 OPEN 启动的"中文名 → package"映射问题，缩小视觉兜底使用范围。

**方案：** Android PackageManager + `queryIntentActivities(MAIN/LAUNCHER)` + `loadLabel(pm)` 在手机端读"桌面图标名"。

**实现路径（分阶段）：**

#### Stage 1：helper APK 验证（优先）
- 创建 `android/` Gradle 工程（与 phone_agent 平级）
- `applicationId=com.phoneagent.app`，minSdk26 / target34，零三方依赖
- exported Activity（无 LAUNCHER filter、透明主题、后台线程查询）
- 输出 `getExternalFilesDir/applist.json`（tmp → rename + `.done` 标记）
- PC 端 `adb pull`；fallback = JSON 分块打到 logcat tag `PA_APPLIST`
- 手动验证：抖音 / 哔哩哔哩等中文名 + 包名正确

#### Stage 2：phone_agent 集成
- 新增 `device/android/app_index.py`：`AppIndex` 类
- 集成 helper APK：启动 Activity → 轮询 `.done` / pull / parse → 缓存
- `AppLauncher` 新增 L0.5 层：learned cache 和 L1 静态表之间插入 AppIndex 查询
- 静态表保留（快速路径 + 兜底）

#### Stage 3：最终迁移（on-device APP 时）
- helper APK 逻辑直接长进主 App（Kotlin Service / Helper 类）
- AppIndex 改为直接调用 PackageManager API，不再走 ADB
- 持久化：`~/.phone_agent/learned_apps.json` → App 内部存储

**构建环境要求：**
- 本机仅 JDK 17，无 Android SDK / Gradle / Studio
- 需装 Android SDK（cmdline-tools → build-tools + platform）
- Android Studio 与 CLI 工具共用 ANDROID_HOME，装哪个都不返工

详见 2026-06-08 会话记忆。

---

### 2. 视觉兜底 Iteration 3 验证

**待测场景：** 打开"李跳跳"（在桌面"系统工具"文件夹内）

**验证点：**
- 模型识别"系统工具"文件夹
- CLICK 展开文件夹
- 找到李跳跳后 CLICK 启动
- Runner 触发 `learn_app_from_visual("李跳跳", "cn.litiaotiao.app")` 写入 cache
- 下次"打开李跳跳"秒开（走 learned 路径）

**如果失败：** 看 trace 找新的 prompt 缺口，继续迭代。

---

### 3. prompt 优化（观察到的问题）

**模型保险性重复点击：**
- B 站任务 step 4-5 重复点搜索框，7-8 重复点搜索按钮
- 任务能完成但低效

**优化方向：** Prompt 加"刚才点过的位置不用再点，等待页面响应，不响应再 WAIT"。

---

### 4. 测试覆盖扩展

**当前：** 42 单元测试 + 2 个真机场景（打开抖音、B 站搜索）

**待补充：**
- 敏感动作拦截真机验证（美团下单、支付宝转账）
- 视觉兜底真机回归（李跳跳、冷门 app）
- 复杂多步任务（对应比赛 11 条样例的真实版本）
- 异常场景（网络断开、app 崩溃、权限拒绝）

---

## 中期方向

### 1. 多轮对话 + 任务澄清

**当前：** 单轮指令 → 执行 → 完成

**目标：** 
- 指令不清晰时主动澄清（"你要买哪家店的？"）
- 任务执行中遇到歧义时询问用户（"有多个结果，要哪个？"）
- 支持多轮交互式任务

**实现要点：**
- Runner 支持暂停 / 恢复
- Reasoner 新增 `ASK_USER` 动作
- CLI 支持交互式输入

---

### 2. 用户偏好持久化

**场景：**
- 常用地址（外卖默认地址）
- 常用账号（支付宝 / 微信切换）
- 操作习惯（跳过广告 vs 看完广告）

**实现：** `~/.phone_agent/preferences.json`

---

### 3. Web UI 前端

**目标：** 非技术用户友好界面

**功能：**
- 任务输入框
- 实时截图 + 动作可视化
- 历史任务列表 + 回放
- 敏感动作确认弹窗

**技术栈：** 待定（Flask + Vue / Gradio / Streamlit）

---

### 4. 跨平台支持

**扩展点已预留：** `device/base.py` Protocol

**候选平台：**
- `device/web/` — Selenium / Playwright 浏览器自动化
- `device/desktop/` — pyautogui / Windows UI Automation
- `device/ios/` — Appium / WebDriverAgent（需 macOS）

---

## 长期愿景

### 1. on-device APP 完整实现

**核心组件：**
- **Accessibility Service** — 替代 uiautomator2，直接读取 UI 树 + 注入手势
- **截图服务** — MediaProjection API，无需 ADB
- **PackageManager** — 应用名解析、启动、查询
- **前台 Activity** — 任务配置、历史查看、用户确认
- **后台 Service** — 长驻守护，接收任务指令

**技术栈：** Kotlin + Jetpack Compose + Room + WorkManager

**模型部署：**
- **云端推理**（当前方案）：HTTPS 调用 Doubao API，灵活但依赖网络
- **on-device 推理**（未来可选）：ONNX / TFLite / MediaPipe，隐私优先但模型能力受限

---

### 2. 多模态能力扩展

**当前：** 视觉输入（截图）→ 文本输出（动作）

**扩展方向：**
- **语音输入** — 语音 → 文本 → 任务（Google Speech API / 讯飞）
- **语音输出** — 任务进度 / 结果播报（TTS）
- **OCR 增强** — 复杂场景文本识别（PaddleOCR / Google ML Kit）

---

### 3. 任务模板 + Playbook

**目标：** 高频任务模板化，降低推理成本

**实现：**
- 用户标注"这次操作很好，保存为模板"
- 提取关键路径 → 生成 playbook（条件分支 + 兜底）
- 下次同类任务优先匹配 playbook，只在分支点调模型

**示例：**
- "美团外卖下单" playbook：OPEN 美团 → CLICK 外卖 Tab → TYPE 店名 → ...
- 分支点：搜索结果有多个店 → 调模型识别目标店

---

### 4. 安全与隐私

**当前：** 敏感动作前用户确认

**增强方向：**
- **沙盒模式** — 限制动作范围（只能操作指定 app）
- **审计日志** — 所有动作记录 + 截图存档
- **隐私保护** — 截图脱敏（模糊密码框、身份证号）
- **权限最小化** — Accessibility Service 权限按需申请

---

## 已知技术债

### 1. 坐标精度问题

**当前：** 归一化坐标 0-1000，单位约 1.44 像素（1440×3200 设备）

**问题：** 小控件（< 50×50 像素）点击可能偏移

**方案：**
- 提高归一化精度（0-10000）
- 或 perception 层做"点击中心"补偿

---

### 2. 中文输入兼容性

**当前：** `d(focused=True).set_text()` 走 UIAutomator

**已知问题：** 部分输入框不响应（游戏内输入框、WebView）

**方案：**
- fallback 到 ADBKeyboard IME（需手动切输入法）
- 或 Accessibility `ACTION_SET_TEXT`

---

### 3. 动态内容识别

**挑战：** 信息流 / 推荐列表每次内容不同

**当前：** 模型靠位置 / 文本特征识别

**改进方向：**
- OCR 提取关键词定位
- 或 UI 树元素 ID / content-desc 辅助

---

## 相关记忆

- [[product_overview.md]] — 产品定位、当前能力
- [[technical_decisions.md]] — OPEN 启动策略、视觉兜底机制
- [[development_history.md]] — 真机验证结果、已解决问题
- [[collaboration_style.md]] — 协作偏好、不要做的事
