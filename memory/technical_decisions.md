---
name: technical-decisions
description: OPEN 启动策略、视觉兜底机制、坐标体系、模型配置等关键技术决策
metadata:
  type: project
---

# 关键技术决策

更新时间：2026-06-17

---

## OPEN 启动策略演化

### 设计目标

- 不维护"全量"中文名→包名映射表（用户明确反对硬编码）
- 高频 app 秒开（静态表）
- 冷门 app 自动兜底（视觉识别）
- 海外模型输出兼容（alias 表）

### 五级 fallback 最终方案

```
open_app(name_or_package):
  ① learned cache  ~/.seetouch/learned_apps.json (视觉学到的)
  ② L1 静态表      app_table.lookup() (17 高频 app: 抖音/B站/微信/QQ...)
  ③ L1' alias      PACKAGE_ALIASES (TikTok→抖音, Twitter→微博...)
  ④ L2 直通        re.match(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$') && installed
  ⑤ L4 视觉兜底    go_home() + raise OpenAppNeedsVisual
```

**关键：learned cache 只在视觉兜底成功后写入，不在 L1/L2/alias 启动后自动学习。**

**Why：** L1/L2 已是权威映射，学了是冗余；只有视觉兜底是"模型+用户+设备"三方验证过的新映射，值得持久化。

---

## fuzzy 模糊匹配为何移除（2026-05-21 起）

### 原方案（已废弃）

```python
def fuzzy_match(query, candidates):
    # 剥前缀 com./cn./tv. ...
    # difflib.SequenceMatcher 相似度 > 0.75
    # 长度门槛 >= 4 字符
    # 黑名单 {app, main, lite, pro, mobile, ...}
```

### 真机死循环 bug 复盘（2026-05-20）

**症状：** "打开抖音" 连续 12+ 步重复 OPEN，直到用户打断。

**根因链：**
1. 模型输出 `com.zhiliaoapp.musically`（TikTok 海外版）
2. 设备未安装，fuzzy_match 在 447 个包里误匹配到 `com.biquge.ebook.app`（笔趣阁）
   - `com.` 公共前缀让相似度虚高
   - `app` 末尾段仅 3 字符未被黑名单化
3. 错误结果立即写入 cache，后续重试始终用错的
4. 模型识别出"这是笔趣阁不是抖音"，再次 OPEN，Runner 无死循环检测 → 无止境

**修复措施（全部已上线）：**
- **移除 fuzzy_match 整段代码**（从 L3 直接跳到 L4 视觉兜底）
- 新增 PACKAGE_ALIASES 表（TikTok → 抖音、Twitter → 微博等）
- AppLauncher 改为 verify-then-learn（启动后轮询 `current_app()`，通过才写 cache）
- Runner 加 `consecutive_identical_actions=3`，3 步同动作即 abort("stuck_loop")
- Prompt 强调"必须用国内大陆版 package，不要 TikTok"

**Why：** Android 包名公共部分（com./cn./tv./org.）太多，字符串相似度假阳性极高。learned cache 在执行前写入是危险的——一旦误学，永久错误。

**How to apply：** 后续如果再考虑"自动发现 app 映射"，必须：
- 在真机验证成功后才写 cache（verify-then-learn）
- 多步确认前台稳定（不要刚误点别的 app 就学了）
- 或按任务完成度回写（任务 COMPLETE 才认为映射正确）

---

## 视觉兜底机制

### 触发条件

`OpenAppNeedsVisual` 异常 → Runner 捕获后标记 `pending_visual_request` 和 `visual_baseline_app`（当前桌面 package）。

### 学习触发

每步执行后，如果：
- `pending_visual_request` 非空
- 当前动作不是 OPEN
- `current_app()` 切换到非 baseline 的真实 app

则调用 `device.learn_app_from_visual(request, current)` 写入 cache。

### Prompt 引导（三轮迭代）

**Iteration 1（无引导）：** 模型重复 OPEN 同名 app → 死循环。

**Iteration 2（硬规则）：** 
- note 激进措辞："❗ OPEN 'xxx' 失败，本步绝对不要再 OPEN 同名 app，必须 CLICK 桌面图标"
- prompt 加硬规则：历史里看到 `OPEN '<app>' 失败` 字样，本步绝对不能再 OPEN
- 效果：不再死循环，正确 SCROLL 翻页 + 上滑抽屉，但找不到文件夹内的 app

**Iteration 3（桌面文件夹支持）：**
- 桌面文件夹识别：图标内 4/9 个 app 预览 + 外框 + 分组名
- 展开方式：CLICK 文件夹中心
- 退出方式：CLICK 屏幕底部空白（如 `[500,950]`）
- 何时放弃：翻完所有页 + 探索过名字相关的文件夹 + 抽屉滚到底

**Why：** 桌面文件夹是 Android 设备非常普遍的 UI 元素，产品 prompt 不能假设 app 一定有顶层图标。

---

## WAIT 动作协议（2026-06-01 新增）

### 设计初衷

真机测试"在哔哩哔哩搜索采莲曲"时，B 站启动后还在加载页，模型输出：
```json
{"action": "WAIT", "parameters": {}}
```
但协议不支持 WAIT，parser 失败兜底返回 `Action(COMPLETE)`，任务被"假完成"提前终止。

### 实现

- `Action` 新增 `ACTION_WAIT`，参数 `{"seconds": float}` 可选，默认 1.5s
- `Runner._execute(WAIT)` = `time.sleep(clip(seconds, 0.5, 5.0))`
- parser 失败的 fallback **从 COMPLETE 改成 WAIT**（不要让 parse 错误静默"假完成"）
- Prompt 说明：只在"界面加载中 / 动画即将结束 / 弹窗即将消失"场景使用，不要当 fallback

**Why：** 模型有"等一下"的合理需求。静默 fallback 到 COMPLETE 极其危险——任何 parser bug 都会被伪装成"任务完成"，后续无从排查。

**How to apply：** 之后再发现模型输出协议外的 action，优先**加协议**（如 LONG_PRESS、PINCH），不要再让 parser 兜底到 WAIT 之外。

---

## 坐标体系（沿用比赛协议）

- **归一化坐标**：0-1000 区间，与设备分辨率无关
- **perception 层负责转换**：`normalize(pixel_x, pixel_y, width, height)` / `denormalize(x, y, width, height)`
- **Why：** 模型已在比赛数据上训练，习惯 0-1000 体系；跨设备泛化能力强

---

## Doubao thinking 模式演化

### 比赛阶段（已结束）
- 强制 `disabled`（BaseAgent 硬编码 `extra_body={"thinking": {"type": "disabled"}}`）
- 原因：比赛规则约束

### 产品阶段（2026-05-21 起）
- 默认 `auto`（模型按需启动 VisualCoT）
- 配置：`SEETOUCH_THINKING_MODE` 环境变量
- 成本监控：`_extract_usage` 带 `reasoning_tokens`

### 真机发现（2026-05-31）
- API 报 400：`Unsupported thinking type for the current model: auto`
- doubao-seed-1-6-vision-250815 只支持 `enabled` / `disabled`
- 改默认为 `enabled`（准确率优先）

### 性能对比（Xiaomi rubens / Android 12）

| thinking_mode | 步均耗时 | 准确率 | 适用场景 |
|---|---|---|---|
| disabled | 3-5s | 中 | 简单任务、成本敏感 |
| enabled | 7-12s | 高 | 复杂场景（小控件、广告识别） |
| auto | - | - | vision 模型不支持 |

**Why：** thinking=enabled 慢 2-3 倍，但识别准确率明显提高（B 站开屏广告自动跳过、复杂搜索场景不再瞎点）。

**How to apply：** 产品默认 `enabled`（准确率优先）；成本敏感场景可切 `disabled`；添加新模型时先探测支持的 thinking 模式集合。

---

## 死循环检测（2026-05-21 新增）

### 机制

`Runner` 维护 `consecutive_identical_actions` 计数器：
- 连续 3 步相同 action + parameters → abort("stuck_loop")
- 不同动作时重置计数器

### 覆盖场景

- OPEN 失败后重复 OPEN（视觉兜底前的死循环）
- WAIT 无限等待
- CLICK 同一位置无响应

**Why：** 首次真机跑遇到 12+ 步 OPEN 死循环，用户手动打断。产品不能依赖人工监控。

---

## 相关记忆

- [[product_overview.md]] — 产品定位、核心能力
- [[development_history.md]] — 死循环 bug 详细复盘、MIUI 踩坑
- [[future_roadmap.md]] — on-device APP 迁移计划、PackageManager 方案
