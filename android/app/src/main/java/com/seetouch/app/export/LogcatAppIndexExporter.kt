package com.seetouch.app.export

import android.util.Log
import org.json.JSONObject

/**
 * logcat 导出：把 JSON 分块打到固定 tag，供 PC 端 `adb logcat -s SEETOUCH_APPLIST` 抓取。
 *
 * 用于 adb pull 不可用（如权限受限的设备）时的兜底通道。
 *
 * 行协议（PC 端依赖，勿随意变更）：
 *   BEGIN <总块数>
 *   CHUNK <序号>/<总块数> <base64 无换行分块>
 *   END <payload 字节数>
 *
 * JSON 先做 base64 再分块，避免多字节 UTF-8 字符被 logcat 行长截断打碎。
 */
class LogcatAppIndexExporter(
    private val chunkSize: Int = DEFAULT_CHUNK_SIZE,
) : AppIndexExporter {

    override val name: String = "logcat"

    override fun export(payload: JSONObject) {
        val bytes = payload.toString().toByteArray(Charsets.UTF_8)
        val encoded = android.util.Base64.encodeToString(
            bytes,
            android.util.Base64.NO_WRAP,
        )
        val chunks = encoded.chunked(chunkSize)
        Log.i(TAG, "BEGIN ${chunks.size}")
        chunks.forEachIndexed { index, chunk ->
            Log.i(TAG, "CHUNK ${index + 1}/${chunks.size} $chunk")
        }
        Log.i(TAG, "END ${bytes.size}")
    }

    companion object {
        const val TAG = "SEETOUCH_APPLIST"

        // logcat 单条日志上限约 4KB，留足 tag / 前缀余量
        private const val DEFAULT_CHUNK_SIZE = 3000
    }
}
