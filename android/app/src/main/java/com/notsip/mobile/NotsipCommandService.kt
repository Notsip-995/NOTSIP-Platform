package com.notsip.mobile

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.*
import okhttp3.*
import org.json.JSONObject

/** Executes only commands received from the paired NOTSIP node. */
class NotsipCommandService(private val service: AccessibilityService) {
    private val client = OkHttpClient()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    fun start(prefs: android.content.SharedPreferences) = scope.launch {
        while (isActive) {
            try {
                val base = prefs.getString("url", "")!!.trimEnd('/')
                val id = prefs.getString("device_id", "")!!
                val token = prefs.getString("token", "")!!
                if (base.isNotBlank() && id.isNotBlank() && token.isNotBlank()) {
                    val req = Request.Builder().url("$base/api/devices/commands?device_id=$id&token=$token").get().build()
                    client.newCall(req).execute().use { r ->
                        if (r.isSuccessful) {
                            val body = JSONObject(r.body?.string() ?: "{}"); val arr = body.optJSONArray("commands") ?: return@use
                            for (i in 0 until arr.length()) execute(arr.getJSONObject(i), base, id, token)
                        }
                    }
                }
            } catch (_: Exception) {}
            delay(2000)
        }
    }
    private fun execute(c: JSONObject, base: String, id: String, token: String) {
        val action = c.optString("action"); val payload = c.optJSONObject("payload") ?: JSONObject(); var ok = false
        when (action) {
            "back" -> ok = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            "home" -> ok = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
            "recents" -> ok = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)
            "notifications" -> ok = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS)
            "lock_screen" -> ok = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN)
            "click_text" -> ok = clickText(service.rootInActiveWindow, payload.optString("text"))
        }
        val result = JSONObject().put("action", action).put("success", ok)
        val body = result.toString().toRequestBody("application/json".toMediaType())
        val rb = JSONObject().put("device_id",id).put("token",token).put("command_id",c.optString("id")).put("status",if(ok)"SUCCESS" else "FAILURE").put("result",result).toString().toRequestBody("application/json".toMediaType())
        client.newCall(Request.Builder().url("$base/api/devices/command-result").post(rb).build()).execute().close()
    }
    private fun clickText(root: AccessibilityNodeInfo?, text: String): Boolean {
        if (root == null || text.isBlank()) return false
        val nodes = root.findAccessibilityNodeInfosByText(text); for (n in nodes) if (n.isClickable && n.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
        return false
    }
}
