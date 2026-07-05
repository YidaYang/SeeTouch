package com.seetouch.app.appindex

/**
 * 应用索引数据源抽象。
 *
 * 当前实现基于 PackageManager；未来 on-device 主 App 可直接复用本接口，
 * 也可扩展出带缓存 / 带增量更新的实现。
 */
interface AppIndexProvider {
    fun queryLaunchableApps(): List<AppEntry>
}
