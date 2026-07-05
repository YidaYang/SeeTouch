"""On-device Android 实现:通过 Chaquopy 调 Kotlin DeviceBridge,不依赖 adb/uiautomator2。

仅在 Android APP 内(Chaquopy 运行时)可用;PC 环境导入 controller 会因缺少
com.seetouch.app java 包而失败,属预期行为。
"""
