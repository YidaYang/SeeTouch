package com.seetouch.app.appindex

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build

/**
 * 基于 PackageManager 的应用索引实现。
 *
 * 通过 queryIntentActivities(MAIN/LAUNCHER) 枚举所有"桌面图标"入口，
 * 与启动器看到的应用集合一致（含桌面文件夹内的 app）。
 */
class PackageManagerAppIndexProvider(context: Context) : AppIndexProvider {

    private val packageManager: PackageManager = context.packageManager

    override fun queryLaunchableApps(): List<AppEntry> {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val resolveInfos = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            packageManager.queryIntentActivities(
                intent,
                PackageManager.ResolveInfoFlags.of(0L),
            )
        } else {
            @Suppress("DEPRECATION")
            packageManager.queryIntentActivities(intent, 0)
        }

        return resolveInfos
            .mapNotNull { resolveInfo ->
                val activityInfo = resolveInfo.activityInfo ?: return@mapNotNull null
                val packageName = activityInfo.packageName ?: return@mapNotNull null
                val label = resolveInfo.loadLabel(packageManager)?.toString()?.trim()
                    .takeUnless { it.isNullOrEmpty() } ?: packageName
                val packageInfo = runCatching {
                    packageManager.getPackageInfo(packageName, 0)
                }.getOrNull()
                val applicationInfo = activityInfo.applicationInfo
                AppEntry(
                    label = label,
                    packageName = packageName,
                    activityName = activityInfo.name ?: "",
                    versionName = packageInfo?.versionName,
                    versionCode = packageInfo?.longVersionCodeCompat ?: 0L,
                    isSystem = applicationInfo?.isSystemApp ?: false,
                    firstInstallTime = packageInfo?.firstInstallTime ?: 0L,
                    lastUpdateTime = packageInfo?.lastUpdateTime ?: 0L,
                )
            }
            // 同一 package 可能有多个 LAUNCHER activity（如支付宝小组件入口），
            // 只保留第一个，避免 PC 端映射时出现同名歧义
            .distinctBy { it.packageName }
            .sortedBy { it.packageName }
    }
}

private val android.content.pm.PackageInfo.longVersionCodeCompat: Long
    get() = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
        longVersionCode
    } else {
        @Suppress("DEPRECATION")
        versionCode.toLong()
    }

private val ApplicationInfo.isSystemApp: Boolean
    get() = flags and (ApplicationInfo.FLAG_SYSTEM or ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0
