package com.notsip.mobile
import android.app.*
import android.content.Intent
import android.net.Uri
import android.os.IBinder
import kotlinx.coroutines.*
import org.json.JSONObject
class NotsipCommandService:Service(){
 private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO);private lateinit var c:NotsipClient
 override fun onCreate(){super.onCreate();c=NotsipClient(this);val nm=getSystemService(NotificationManager::class.java);nm.createNotificationChannel(NotificationChannel("notsip","NOTSIP",NotificationManager.IMPORTANCE_LOW));startForeground(7,Notification.Builder(this,"notsip").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("NOTSIP").setContentText("Device bridge active").setOngoing(true).build());scope.launch{while(isActive){try{c.heartbeat();val a=c.poll().optJSONArray("commands");if(a!=null)for(i in 0 until a.length())exec(a.getJSONObject(i))}catch(_:Exception){};delay(3000)}}}
 private fun exec(x:JSONObject){val id=x.optString("id");val action=x.optString("action");val p=x.optJSONObject("payload")?:JSONObject();try{when(action){"open_url"->startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(p.getString("url"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));"open_app"->packageManager.getLaunchIntentForPackage(p.getString("package"))?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)?.let(::startActivity);"notify"->getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis()%100000).toInt(),Notification.Builder(this,"notsip").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("NOTSIP").setContentText(p.optString("text","NOTSIP")).build());"click_text"->{val s=NotsipAccessibilityServiceHolder.instance;if(s==null||!s.clickText(p.getString("text")))throw IllegalStateException("Accessibility unavailable or target not found")};else->throw IllegalArgumentException("unsupported action")};c.result(id,"SUCCESS",JSONObject().put("action",action))}catch(e:Exception){c.result(id,"FAILURE",JSONObject().put("error",e.message))}}
 override fun onBind(i:Intent?):IBinder?=null;override fun onDestroy(){scope.cancel();super.onDestroy()}
}
