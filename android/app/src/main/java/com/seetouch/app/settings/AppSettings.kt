package com.seetouch.app.settings

import android.content.Context
import org.json.JSONObject

/** 轻量配置存取,与 PC 端 .env 的可配置项对齐。 */
class AppSettings(context: Context) {

    private val prefs =
        context.getSharedPreferences("seetouch_settings", Context.MODE_PRIVATE)

    var apiKey: String
        get() = prefs.getString(KEY_API_KEY, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_API_KEY, value.trim()).apply()

    /** 空串 = 用 seetouch 默认模型。 */
    var modelId: String
        get() = prefs.getString(KEY_MODEL_ID, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_MODEL_ID, value.trim()).apply()

    /** enabled(VisualCoT,最准) / disabled(最快最省)。 */
    var thinkingMode: String
        get() = prefs.getString(KEY_THINKING_MODE, "enabled").orEmpty()
        set(value) = prefs.edit().putString(KEY_THINKING_MODE, value).apply()

    var maxSteps: Int
        get() = prefs.getInt(KEY_MAX_STEPS, 45)
        set(value) = prefs.edit().putInt(KEY_MAX_STEPS, value).apply()

    /** 组装 task_entry.run_task 需要的运行配置 JSON。 */
    fun toTaskConfigJson(): String =
        JSONObject()
            .put("api_key", apiKey)
            .put("model_id", modelId)
            .put("thinking_mode", thinkingMode)
            .put("max_steps", maxSteps)
            .toString()

    companion object {
        private const val KEY_API_KEY = "doubao_api_key"
        private const val KEY_MODEL_ID = "doubao_model_id"
        private const val KEY_THINKING_MODE = "thinking_mode"
        private const val KEY_MAX_STEPS = "max_steps"
    }
}
