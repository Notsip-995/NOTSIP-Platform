package com.notsip.mobile
import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.IBinder
import android.telephony.SmsManager
import kotlinx.coroutines.*
import org.json.JSONObject
class NotsipCommandService:Service(){
 private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO);private lateinit var c:NotsipClient
 private var backoff=3000L
 override fun onCreate(){super.onCreate();c=NotsipClient(this);val nm=getSystemService(NotificationManager::class.java);nm.createNotificationChannel(NotificationChannel("notsip","NOTSIP",NotificationManager.IMPORTANCE_LOW));startForeground(7,Notification.Builder(this,"notsip").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("NOTSIP").setContentText("Device bridge active").setOngoing(true).build());scope.launch{while(isActive){try{c.heartbeat();val a=c.poll().optJSONArray("commands");if(a!=null)for(i in 0 until a.length())exec(a.getJSONObject(i));backoff=3000L}catch(_:Exception){backoff=minOf(backoff*2,60000L)};delay(backoff)}}}
 private fun exec(x:JSONObject){val id=x.optString("id");val action=x.optString("action");val p=x.optJSONObject("payload")?:JSONObject();try{
   var status="SUCCESS";var verified=true;var note=""
   when(action){
    "open_url"->{startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(p.getString("url"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));status="PARTIAL_SUCCESS";verified=false;note="Android accepted the activity launch request; destination UI state was not independently verified"}
    "open_app"->{packageManager.getLaunchIntentForPackage(p.getString("package"))?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)?.let(::startActivity)?:throw IllegalArgumentException("package not launchable");status="PARTIAL_SUCCESS";verified=false;note="Android accepted the application launch request; foreground application state was not independently verified"}
    "notify"->getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis()%100000).toInt(),Notification.Builder(this,"notsip").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("NOTSIP").setContentText(p.optString("text","NOTSIP")).build())
    "click_text"->{val s=NotsipAccessibilityServiceHolder.instance;if(s==null||!s.clickText(p.getString("text")))throw IllegalStateException("Accessibility unavailable or target not found")}
    "make_call"->{requirePermission(Manifest.permission.CALL_PHONE);startActivity(Intent(Intent.ACTION_CALL,Uri.parse("tel:"+p.getString("number"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));status="PARTIAL_SUCCESS";verified=false;note="Android accepted the call intent; remote-party connection state was not independently verified"}
    "send_sms"->{requirePermission(Manifest.permission.SEND_SMS);val number=p.getString("number");val text=p.getString("text");SmsManager.getDefault().sendTextMessage(number,null,text,null,null);status="PARTIAL_SUCCESS";verified=false;note="Android accepted the SMS send request; carrier delivery was not independently verified"}
    else->throw IllegalArgumentException("unsupported action")
   }
   val result=JSONObject().put("action",action).put("verified",verified);if(note.isNotEmpty())result.put("note",note);c.result(id,status,result)
  }catch(e:Exception){c.result(id,"FAILURE",JSONObject().put("error",e.message).put("action",action).put("verified",false))}}
 private fun requirePermission(permission:String){if(checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED)throw SecurityException("Android permission not granted: $permission")}
 override fun onBind(i:Intent?):IBinder?=null;override fun onDestroy(){scope.cancel();super.onDestroy()}
}
