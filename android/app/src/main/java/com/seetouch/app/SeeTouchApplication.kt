package com.seetouch.app

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.seetouch.app.bridge.DeviceBridge

class SeeTouchApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        DeviceBridge.init(this)
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
    }
}
