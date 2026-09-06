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
class NotsipClient(private val ctx:Context){
 private val p=ctx.getSharedPreferences("notsip",Context.MODE_PRIVATE);private val http=OkHttpClient()
 fun baseUrl()=p.getString("base","http://10.0.2.2:8765")!!
 fun setBaseUrl(v:String){p.edit().putString("base",v.trimEnd('/')).apply()}
 fun deviceId()=p.getString("device","android-${UUID.randomUUID()}")!!.also{p.edit().putString("device",it).apply()}
 fun setDeviceId(v:String){p.edit().putString("device",v).apply()}
 fun token()=p.getString("token","")!!
 suspend fun pair(code:String){val body=JSONObject().put("code",code).put("device_id",deviceId()).put("name","NOTSIP Android").put("platform","android").toString();val r=JSONObject(req("POST","/api/pair/consume",body));p.edit().putString("token",r.getString("token")).apply()}
 fun heartbeat(){req("POST","/api/devices/heartbeat?device_id=${deviceId()}&token=${token()}",null)}
 fun poll()=JSONObject(req("GET","/api/devices/${deviceId()}/commands?token=${token()}",null))
 fun result(id:String,status:String,result:JSONObject){req("POST","/api/devices/result",JSONObject().put("command_id",id).put("status",status).put("result",result).toString())}
 fun transcribe(bytes:ByteArray,mime:String="audio/mp4",language:String=""):JSONObject{val mediaType=mime.toMediaType();val body=MultipartBody.Builder().setType(MultipartBody.FORM).addFormDataPart("language",language).addFormDataPart("file","voice.m4a",RequestBody.create(mediaType,bytes)).build();return JSONObject(req("POST","/api/voice/transcribe",null,body))}
 fun perceive(jpeg:ByteArray,prompt:String=""):JSONObject{val b=Base64.encodeToString(jpeg,Base64.NO_WRAP);return JSONObject(req("POST","/api/perception/frame",JSONObject().put("image_base64",b).put("mime","image/jpeg").put("prompt",prompt).toString()))}
 private fun req(m:String,path:String,body:String?,requestBody:RequestBody?=null):String{val rb=Request.Builder().url(baseUrl()+path);if(m=="POST"){val rbod=requestBody?:body?.let{RequestBody.create("application/json".toMediaType(),it)}?:RequestBody.create(null,ByteArray(0));rb.post(rbod)}else rb.get();http.newCall(rb.build()).execute().use{if(!it.isSuccessful)throw RuntimeException("HTTP ${it.code}");return it.body!!.string()}}
}
