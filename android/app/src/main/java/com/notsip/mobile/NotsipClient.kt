package com.notsip.mobile

import android.content.Context
import android.util.Base64
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import org.json.JSONObject
import java.util.UUID

class NotsipClient(private val ctx: Context) {
    private val prefs = ctx.getSharedPreferences("notsip", Context.MODE_PRIVATE)
    private val http = OkHttpClient()

    fun baseUrl(): String = prefs.getString("base", "http://10.0.2.2:8765") ?: "http://10.0.2.2:8765"
    fun setBaseUrl(value: String) = prefs.edit().putString("base", value.trimEnd('/')).apply()

    fun deviceId(): String {
        val existing = prefs.getString("device", null)
        if (!existing.isNullOrBlank()) return existing
        val id = "android-${UUID.randomUUID()}"
        prefs.edit().putString("device", id).apply()
        return id
    }

    fun setDeviceId(value: String) = prefs.edit().putString("device", value).apply()
    fun token(): String = prefs.getString("token", "") ?: ""

    suspend fun pair(code: String) {
        val body = JSONObject()
            .put("code", code)
            .put("device_id", deviceId())
            .put("name", "NOTSIP Android")
            .put("platform", "android")
            .toString()
        val response = JSONObject(request("POST", "/api/pair/consume", body))
        prefs.edit().putString("token", response.getString("token")).apply()
    }

    fun heartbeat() {
        request("POST", "/api/devices/heartbeat?device_id=${deviceId()}&token=${token()}", null)
    }

    fun poll(): JSONObject = JSONObject(
        request("GET", "/api/devices/${deviceId()}/commands?token=${token()}", null)
    )

    fun result(commandId: String, status: String, result: JSONObject) {
        val body = JSONObject()
            .put("command_id", commandId)
            .put("status", status)
            .put("result", result)
            .toString()
        request("POST", "/api/devices/result", body, null, deviceHeaders())
    }

    fun transcribe(bytes: ByteArray, mime: String = "audio/mp4", language: String = ""): JSONObject {
        val mediaType = mime.toMediaType()
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("language", language)
            .addFormDataPart("file", "voice.m4a", RequestBody.create(mediaType, bytes))
            .build()
        return JSONObject(request("POST", "/api/voice/transcribe", null, body))
    }

    fun perceive(jpeg: ByteArray, prompt: String = ""): JSONObject {
        val encoded = Base64.encodeToString(jpeg, Base64.NO_WRAP)
        val body = JSONObject()
            .put("image_base64", encoded)
            .put("mime", "image/jpeg")
            .put("prompt", prompt)
            .toString()
        return JSONObject(request("POST", "/api/perception/frame", body))
    }

    private fun deviceHeaders(): Map<String, String> = mapOf(
        "X-NOTSIP-Device-ID" to deviceId(),
        "X-NOTSIP-Device-Token" to token()
    )

    private fun request(
        method: String,
        path: String,
        body: String?,
        requestBody: RequestBody? = null,
        headers: Map<String, String> = emptyMap()
    ): String {
        val builder = Request.Builder().url(baseUrl() + path)
        headers.forEach { (key, value) -> builder.addHeader(key, value) }
        if (method == "POST") {
            val payload = requestBody ?: body?.let { RequestBody.create("application/json".toMediaType(), it) }
                ?: RequestBody.create(null, ByteArray(0))
            builder.post(payload)
        } else {
            builder.get()
        }
        http.newCall(builder.build()).execute().use { response ->
            if (!response.isSuccessful) throw RuntimeException("HTTP ${response.code}")
            return response.body?.string() ?: "{}"
        }
    }
}
