package com.seetouch.app.helper

import android.app.Activity
import android.os.Bundle
import android.util.Log
import com.seetouch.app.appindex.AppIndexJson
import com.seetouch.app.appindex.PackageManagerAppIndexProvider
import com.seetouch.app.export.AppIndexExporter
import com.seetouch.app.export.FileAppIndexExporter
import com.seetouch.app.export.LogcatAppIndexExporter
import kotlin.concurrent.thread

/**
 * PC 端触发入口：导出本机可启动应用索引。
 *
 * 无 LAUNCHER filter（桌面不可见）、透明主题（不打断前台画面），由 ADB 启动：
 *
 *   adb shell am start -n com.seetouch.app/.helper.AppListExportActivity
 *
 * 可选 extra：
 *   --es channels "file,logcat"   导出通道，默认 file（失败自动兜底 logcat）
 *   --es request_id "<uuid>"      回显到 .done 标记，PC 端用于区分新旧导出
 *
 * 导出完成后 PC 端 pull：
 *   adb pull /sdcard/Android/data/com.seetouch.app/files/applist.json
 *
 * 未来 on-device 主 App：导出逻辑全部在 appindex / export 包，本 Activity
 * 只是 ADB 桥接壳，主 App 直接调用 AppIndexProvider 即可，无需此入口。
 */
class AppListExportActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val channels = intent.getStringExtra(EXTRA_CHANNELS)
            ?.split(',')
            ?.map { it.trim().lowercase() }
            ?.filter { it.isNotEmpty() }
            ?: listOf(CHANNEL_FILE)
        val requestId = intent.getStringExtra(EXTRA_REQUEST_ID).orEmpty()
        thread(name = "seetouch-applist-export") {
            runExport(channels, requestId)
            runOnUiThread { finish() }
        }
    }

    private fun runExport(channels: List<String>, requestId: String) {
        val payload = try {
            val entries = PackageManagerAppIndexProvider(this).queryLaunchableApps()
            AppIndexJson.serialize(entries)
        } catch (t: Throwable) {
            Log.e(TAG, "app index query failed", t)
            return
        }
        Log.i(TAG, "queried ${payload.optInt("count")} launchable apps")

        var fileExportFailed = false
        for (channel in channels) {
            val exporter = createExporter(channel, requestId)
            if (exporter == null) {
                Log.w(TAG, "unknown export channel: $channel")
                continue
            }
            try {
                exporter.export(payload)
                Log.i(TAG, "export ok via ${exporter.name}")
            } catch (t: Throwable) {
                Log.e(TAG, "export failed via ${exporter.name}", t)
                if (exporter.name == CHANNEL_FILE) fileExportFailed = true
            }
        }
        // 文件通道失败时自动兜底 logcat，保证 PC 端总有一条可用通道
        if (fileExportFailed && CHANNEL_LOGCAT !in channels) {
            runCatching { LogcatAppIndexExporter().export(payload) }
                .onSuccess { Log.i(TAG, "export ok via logcat (fallback)") }
                .onFailure { Log.e(TAG, "export failed via logcat (fallback)", it) }
        }
    }

    private fun createExporter(channel: String, requestId: String): AppIndexExporter? = when (channel) {
        CHANNEL_FILE -> FileAppIndexExporter(
            getExternalFilesDir(null) ?: filesDir,
            requestId = requestId,
        )
        CHANNEL_LOGCAT -> LogcatAppIndexExporter()
        else -> null
    }

    companion object {
        const val TAG = "SEETOUCH_HELPER"
        const val EXTRA_CHANNELS = "channels"
        const val EXTRA_REQUEST_ID = "request_id"
        const val CHANNEL_FILE = "file"
        const val CHANNEL_LOGCAT = "logcat"
    }
}
