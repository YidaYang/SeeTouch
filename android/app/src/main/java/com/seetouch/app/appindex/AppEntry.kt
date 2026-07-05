package com.seetouch.app.appindex

/**
 * 一条"桌面可启动应用"记录。
 *
 * label 即用户在桌面看到的应用名（loadLabel 结果，跟随系统语言），
 * 是 SeeTouch OPEN 动作"中文名 → package"映射的权威来源。
 */
data class AppEntry(
    val label: String,
    val packageName: String,
    val activityName: String,
    val versionName: String?,
    val versionCode: Long,
    val isSystem: Boolean,
    val firstInstallTime: Long,
    val lastUpdateTime: Long,
)
