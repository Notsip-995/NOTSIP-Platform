package com.notsip.mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class NotsipBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            val service = Intent(context, NotsipCommandService::class.java)
            try {
                context.startForegroundService(service)
            } catch (_: Exception) {
            }
        }
    }
}
