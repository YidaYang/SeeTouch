# SeeTouch Android

SeeTouch 的 Android 端工程。当前阶段是 **helper APK**（Stage 1）：为 PC 端提供"桌面应用名 → package"权威索引；所有组件都按"将来长进独立 on-device 主 App"的标准设计。

## 模块结构

```
app/src/main/java/com/seetouch/app/
├── appindex/    # 应用索引领域层（主 App 直接复用）
│   ├── AppEntry.kt                      # 单条应用记录
│   ├── AppIndexProvider.kt              # 数据源抽象
│   ├── PackageManagerAppIndexProvider.kt # PackageManager 实现
│   └── AppIndexJson.kt                  # 版本化 JSON 序列化（schema_version）
├── export/      # 导出通道层（可插拔）
│   ├── AppIndexExporter.kt              # 通道抽象
│   ├── FileAppIndexExporter.kt          # 文件通道（tmp → rename + .done 标记）
│   └── LogcatAppIndexExporter.kt        # logcat 兜底通道（base64 分块）
└── helper/      # PoC 阶段的 ADB 桥接壳（主 App 阶段可弃用）
    └── AppListExportActivity.kt         # exported 透明 Activity
```

## 构建

```bash
cd android
./gradlew assembleDebug
# 产物: app/build/outputs/apk/debug/app-debug.apk
```

## 使用（PC 端）

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk

# 一键触发 + 拉取 + 校验（仓库根目录）
python scripts/pull_applist.py

# 或手动操作
adb shell am start -n com.seetouch.app/.helper.AppListExportActivity
adb pull /sdcard/Android/data/com.seetouch.app/files/applist.json
```

## 导出协议

### 文件通道（默认）

写入 `getExternalFilesDir()/applist.json`：先写 `.tmp` → 原子 rename → 写 `applist.json.done` 状态标记。PC 端轮询 `.done` 出现后再 pull，避免读到半截文件。

### logcat 兜底通道

`adb pull` 不可用时使用，tag 为 `SEETOUCH_APPLIST`，行协议：

```
BEGIN <总块数>
CHUNK <序号>/<总块数> <base64 分块>
END <payload 字节数>
```

触发方式：`adb shell am start -n com.seetouch.app/.helper.AppListExportActivity --es channels logcat`（文件通道失败时也会自动兜底）。

### JSON 格式（schema_version = 1）

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-05T12:00:00Z",
  "device": {"sdk_int": 34, "manufacturer": "Xiaomi", "model": "...", "locale": "zh-CN"},
  "count": 447,
  "apps": [
    {
      "label": "抖音",
      "package": "com.ss.android.ugc.aweme",
      "activity": "com.ss.android.ugc.aweme.splash.SplashActivity",
      "version_name": "28.0.0",
      "version_code": 280000,
      "system": false,
      "first_install_time": 0,
      "last_update_time": 0
    }
  ]
}
```

字段变更时递增 `schema_version`，不要原地改语义。

## 后续演进（见 memory/future_roadmap.md）

- **Stage 2**：PC 端 `seetouch/device/android/app_index.py` 集成本索引，作为 OPEN 启动策略的 L0.5 层
- **Stage 3**：on-device 主 App —— `appindex/`、`export/` 直接复用，`helper/` 桥接壳由 App 内直接调用 `AppIndexProvider` 替代
