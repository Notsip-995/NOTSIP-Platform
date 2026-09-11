package com.notsip.mobile
import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.IBinder
import android.telephony.SmsManager
import kotlinx.coroutines.*
import org.json.JSONException
import org.json.JSONObject
import java.util.UUID

class NotsipCommandService:Service(){
 private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO);private lateinit var c:NotsipClient
 private var backoff=3000L
 private val commandPrefs by lazy { getSharedPreferences("notsip_commands",MODE_PRIVATE) }
 private fun completed():MutableSet<String>=commandPrefs.getStringSet("completed",emptySet())?.toMutableSet()?:mutableSetOf()
 private fun markCompleted(id:String){val done=completed();done.add(id);while(done.size>256)done.remove(done.first());commandPrefs.edit().putStringSet("completed",done).apply()}
 private fun pendingIds():List<String> = commandPrefs.all.keys.filter{it.startsWith("pending_result_")}.map{it.removePrefix("pending_result_")}
 private fun queueResult(id:String,status:String,result:JSONObject){check(commandPrefs.edit().putString("pending_result_$id",JSONObject().put("status",status).put("result",result.toString()).toString()).commit()){"Failed to persist pending command result"}}
 private fun flushResults(){
  for(id in pendingIds()){
   val raw=commandPrefs.getString("pending_result_$id",null)?:continue
   try{
    val item=JSONObject(raw);c.result(id,item.getString("status"),JSONObject(item.getString("result")));commandPrefs.edit().remove("pending_result_$id").apply();markCompleted(id)
   }catch(_:JSONException){
    val failure=JSONObject().put("error","Android pending command result was locally corrupted").put("action","unknown").put("verified",false)
    try{c.result(id,"FAILURE",failure);commandPrefs.edit().remove("pending_result_$id").apply();markCompleted(id)}catch(_:Exception){return}
   }catch(_:Exception){return}
  }
 }
 override fun onCreate(){super.onCreate();c=NotsipClient(this);val nm=getSystemService(NotificationManager::class.java);nm.createNotificationChannel(NotificationChannel("notsip","NOTSIP",NotificationManager.IMPORTANCE_LOW));startForeground(7,Notification.Builder(this,"notsip").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("NOTSIP").setContentText("Device bridge active").setOngoing(true).build());scope.launch{while(isActive){try{flushResults();c.heartbeat();val a=c.poll().optJSONArray("commands");if(a!=null)for(i in 0 until a.length())exec(a.getJSONObject(i));flushResults();backoff=3000L}catch(_:Exception){backoff=minOf(backoff*2,60000L)};delay(backoff)}}}
 private fun exec(x:JSONObject){val id=x.optString("id");val action=x.optString("action");val p=x.optJSONObject("payload")?:JSONObject();if(id.isBlank())return;if(completed().contains(id))return;try{
   var status="SUCCESS";var verified=true;var note=""
   when(action){
    "open_url"->{startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(p.getString("url"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));status="PARTIAL_SUCCESS";verified=false;note="Android accepted the activity launch request; destination UI state was not independently verified"}
    "open_app"->{packageManager.getLaunchIntentForPackage(p.getString("package"))?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)?.let(::startActivity)?:throw IllegalArgumentException("package not launchable");status="PARTIAL_SUCCESS";verified=false;note="Android accepted the application launch request; foreground application state was not independently verified"}
    "notify"->getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis()%100000).toInt(),Notification.Builder(this,"notsip").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(p.optString("title","NOTSIP")).setContentText(p.optString("body",p.optString("text","NOTSIP"))).build())
    "click_text"->{val s=NotsipAccessibilityServiceHolder.instance;if(s==null||!s.clickText(p.getString("text")))throw IllegalStateException("Accessibility unavailable or target not found")}
    "make_call"->{requirePermission(Manifest.permission.CALL_PHONE);startActivity(Intent(Intent.ACTION_CALL,Uri.parse("tel:"+p.getString("number"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));status="PARTIAL_SUCCESS";verified=false;note="Android accepted the call intent; remote-party connection state was not independently verified"}
    "send_sms"->{requirePermission(Manifest.permission.SEND_SMS);val number=p.getString("number");val text=p.getString("text");SmsManager.getDefault().sendTextMessage(number,null,text,null,null);status="PARTIAL_SUCCESS";verified=false;note="Android accepted the SMS send request; carrier delivery was not independently verified"}
    else->throw IllegalArgumentException("unsupported action")
   }
   val result=JSONObject().put("action",action).put("verified",verified);if(note.isNotEmpty())result.put("note",note);queueResult(id,status,result);flushResults()
  }catch(e:Exception){val result=JSONObject().put("error",e.message).put("action",action).put("verified",false);queueResult(id,"FAILURE",result);flushResults()}}
 private fun requirePermission(permission:String){if(checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED)throw SecurityException("Android permission not granted: $permission")}
 override fun onBind(i:Intent?):IBinder?=null;override fun onDestroy(){scope.cancel();super.onDestroy()}
}
