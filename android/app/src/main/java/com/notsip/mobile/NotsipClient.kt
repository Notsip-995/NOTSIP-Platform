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
    private val secure = SecurePrefs(ctx)
    private val http = OkHttpClient()

    fun baseUrl(): String = prefs.getString("base", "") ?: ""
    fun setBaseUrl(value: String) = prefs.edit().putString("base", value.trimEnd('/')).apply()

    fun deviceId(): String {
        val existing = prefs.getString("device", null)
        if (!existing.isNullOrBlank()) return existing
        val id = "android-${UUID.randomUUID()}"
        prefs.edit().putString("device", id).apply()
        return id
    }

    fun setDeviceId(value: String) = prefs.edit().putString("device", value).apply()

    fun token(): String {
        val protected = secure.getString("token", "")
        if (protected.isNotBlank()) return protected
        val legacy = prefs.getString("token", "") ?: ""
        if (legacy.isNotBlank()) {
            secure.putString("token", legacy)
            prefs.edit().remove("token").apply()
        }
        return legacy
    }

    private fun setToken(value: String) {
        secure.putString("token", value)
        prefs.edit().remove("token").apply()
    }

    suspend fun pair(code: String) {
        require(baseUrl().startsWith("http://") || baseUrl().startsWith("https://")) { "Configure the NOTSIP server URL first" }
        val body = JSONObject()
            .put("code", code)
            .put("device_id", deviceId())
            .put("name", "NOTSIP Android")
            .put("platform", "android")
            .toString()
        val response = JSONObject(request("POST", "/api/pair/consume", body))
        setToken(response.getString("token"))
    }

    fun heartbeat() {
        requireConfigured()
        request("POST", "/api/devices/heartbeat", null, null, deviceHeaders())
    }

    fun poll(): JSONObject {
        requireConfigured()
        return JSONObject(request("GET", "/api/devices/${deviceId()}/commands", null, null, deviceHeaders()))
    }

    fun result(commandId: String, status: String, result: JSONObject) {
        requireConfigured()
        val body = JSONObject()
            .put("command_id", commandId)
            .put("status", status)
            .put("result", result)
            .toString()
        request("POST", "/api/devices/result", body, null, deviceHeaders())
    }

    fun transcribe(bytes: ByteArray, mime: String = "audio/mp4", language: String = ""): JSONObject {
        requireConfigured()
        val mediaType = mime.toMediaType()
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("language", language)
            .addFormDataPart("file", "voice.m4a", RequestBody.create(mediaType, bytes))
            .build()
        return JSONObject(request("POST", "/api/voice/transcribe", null, body, deviceHeaders()))
    }

    fun perceive(jpeg: ByteArray, prompt: String = ""): JSONObject {
        requireConfigured()
        val encoded = Base64.encodeToString(jpeg, Base64.NO_WRAP)
        val body = JSONObject()
            .put("image_base64", encoded)
            .put("mime", "image/jpeg")
            .put("prompt", prompt)
            .toString()
        return JSONObject(request("POST", "/api/perception/frame", body, null, deviceHeaders()))
    }

    private fun requireConfigured() {
        require(baseUrl().startsWith("http://") || baseUrl().startsWith("https://")) { "Configure the NOTSIP server URL first" }
        require(token().isNotBlank()) { "Pair this device with NOTSIP first" }
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
