package com.seetouch.app.task

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.util.Log
import kotlin.concurrent.thread

/**
 * 前台 Service:承载任务执行线程,保证用户切走(任务操作其他 app 时
 * SeeTouch 必然退到后台)后进程不被系统回收。
 */
class TaskExecutionService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val instruction = intent?.getStringExtra(EXTRA_INSTRUCTION)
        val configJson = intent?.getStringExtra(EXTRA_CONFIG_JSON)
        if (instruction.isNullOrBlank() || configJson.isNullOrBlank()) {
            Log.w(TAG, "missing instruction/config, stop")
            stopSelf(startId)
            return START_NOT_STICKY
        }
        if (TaskController.isRunning) {
            Log.w(TAG, "task already running, ignore new request")
            return START_NOT_STICKY
        }

        startForeground(NOTIFICATION_ID, buildNotification(instruction))
        thread(name = "seetouch-task") {
            try {
                TaskController.executeBlocking(instruction, configJson)
            } finally {
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf(startId)
            }
        }
        return START_NOT_STICKY
    }

    private fun buildNotification(instruction: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID, "任务执行", NotificationManager.IMPORTANCE_LOW
            )
        )
        val contentIntent = PendingIntent.getActivity(
            this, 0,
            packageManager.getLaunchIntentForPackage(packageName),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle("SeeTouch 正在执行任务")
            .setContentText(instruction)
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val TAG = "SeeTouchTaskSvc"
        private const val CHANNEL_ID = "seetouch_task"
        private const val NOTIFICATION_ID = 1
        const val EXTRA_INSTRUCTION = "instruction"
        const val EXTRA_CONFIG_JSON = "config_json"

        fun start(context: Context, instruction: String, taskConfigJson: String) {
            val intent = Intent(context, TaskExecutionService::class.java)
                .putExtra(EXTRA_INSTRUCTION, instruction)
                .putExtra(EXTRA_CONFIG_JSON, taskConfigJson)
            context.startForegroundService(intent)
        }
    }
}
