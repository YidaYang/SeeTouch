package com.seetouch.app.export

import org.json.JSONObject
import java.io.File
import java.io.IOException

/**
 * 文件导出：写到 app 外部私有目录（getExternalFilesDir），供 PC 端 adb pull。
 *
 * 写入协议（PC 端依赖，勿随意变更）：
 * 1. 先写临时文件 applist.json.tmp
 * 2. 原子 rename 为 applist.json
 * 3. 最后写 applist.json.done 标记（内容为状态 JSON）
 *
 * PC 端轮询 .done 文件出现后再 pull applist.json，避免读到半截文件。
 */
class FileAppIndexExporter(private val directory: File) : AppIndexExporter {

    override val name: String = "file"

    val outputFile: File get() = File(directory, FILE_NAME)
    val doneFile: File get() = File(directory, DONE_FILE_NAME)

    override fun export(payload: JSONObject) {
        if (!directory.isDirectory && !directory.mkdirs()) {
            throw IOException("cannot create directory: $directory")
        }
        doneFile.delete()
        val tmpFile = File(directory, TMP_FILE_NAME)
        tmpFile.writeText(payload.toString(2), Charsets.UTF_8)
        if (!tmpFile.renameTo(outputFile)) {
            throw IOException("rename failed: $tmpFile -> $outputFile")
        }
        val status = JSONObject()
            .put("status", "ok")
            .put("count", payload.optInt("count"))
            .put("generated_at", payload.optString("generated_at"))
        doneFile.writeText(status.toString(), Charsets.UTF_8)
    }

    companion object {
        const val FILE_NAME = "applist.json"
        const val TMP_FILE_NAME = "applist.json.tmp"
        const val DONE_FILE_NAME = "applist.json.done"
    }
}
