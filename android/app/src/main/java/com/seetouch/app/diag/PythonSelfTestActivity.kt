package com.seetouch.app.diag

import android.app.Activity
import android.os.Bundle
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread

/**
 * Python 运行时自检入口(诊断用,无 LAUNCHER filter),由 ADB 触发:
 *
 *   adb shell am start -n com.seetouch.app/.diag.PythonSelfTestActivity \
 *       [--es api_key "<DOUBAO_API_KEY>"]
 *
 * 结果 JSON 报告打到 logcat tag SEETOUCH_PY(可能较长,分块输出):
 *
 *   adb logcat -s SEETOUCH_PY
 *
 * 带 api_key 时额外做一次真实 Doubao 推理,覆盖 openai SDK / HTTPS 全链路。
 */
class PythonSelfTestActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val apiKey = intent.getStringExtra(EXTRA_API_KEY).orEmpty()
        thread(name = "seetouch-py-selftest") {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this))
                }
                val report = Python.getInstance()
                    .getModule("seetouchapp.selftest")
                    .callAttr("run", apiKey)
                    .toString()
                logChunked(report)
            } catch (t: Throwable) {
                Log.e(TAG, "selftest crashed", t)
            }
            runOnUiThread { finish() }
        }
    }

    private fun logChunked(text: String) {
        Log.i(TAG, "BEGIN")
        text.chunked(3000).forEach { Log.i(TAG, it) }
        Log.i(TAG, "END")
    }

    companion object {
        const val TAG = "SEETOUCH_PY"
        const val EXTRA_API_KEY = "api_key"
    }
}
