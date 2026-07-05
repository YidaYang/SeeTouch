package com.seetouch.app.export

import org.json.JSONObject

/**
 * 应用索引导出通道抽象。
 *
 * 当前有文件导出（PC 端 adb pull）和 logcat 导出（pull 不可用时的兜底）两种实现；
 * 未来 on-device 主 App 可加内部存储 / ContentProvider / 网络上报等实现。
 */
interface AppIndexExporter {
    val name: String

    fun export(payload: JSONObject)
}
