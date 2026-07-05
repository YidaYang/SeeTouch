package com.seetouch.app.appindex

import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * 应用索引的 JSON 序列化。
 *
 * schema_version 用于 PC 端（seetouch device/android/app_index.py）做兼容判断，
 * 字段变更时递增版本号，不要原地改语义。
 */
object AppIndexJson {

    const val SCHEMA_VERSION = 1

    fun serialize(entries: List<AppEntry>): JSONObject {
        val apps = JSONArray()
        for (entry in entries) {
            apps.put(
                JSONObject()
                    .put("label", entry.label)
                    .put("package", entry.packageName)
                    .put("activity", entry.activityName)
                    .put("version_name", entry.versionName ?: JSONObject.NULL)
                    .put("version_code", entry.versionCode)
                    .put("system", entry.isSystem)
                    .put("first_install_time", entry.firstInstallTime)
                    .put("last_update_time", entry.lastUpdateTime),
            )
        }
        return JSONObject()
            .put("schema_version", SCHEMA_VERSION)
            .put("generated_at", isoUtcNow())
            .put(
                "device",
                JSONObject()
                    .put("sdk_int", Build.VERSION.SDK_INT)
                    .put("manufacturer", Build.MANUFACTURER)
                    .put("model", Build.MODEL)
                    .put("locale", Locale.getDefault().toLanguageTag()),
            )
            .put("count", entries.size)
            .put("apps", apps)
    }

    private fun isoUtcNow(): String {
        val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        format.timeZone = TimeZone.getTimeZone("UTC")
        return format.format(Date())
    }
}
