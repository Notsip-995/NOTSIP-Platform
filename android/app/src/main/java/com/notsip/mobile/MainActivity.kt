package com.notsip.mobile
import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.media.MediaRecorder
import android.os.Bundle
import android.provider.MediaStore
import android.widget.*
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream

class MainActivity:Activity(){
 private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Main.immediate)
 private lateinit var client:NotsipClient; private var recorder:MediaRecorder?=null; private var recordingPath=""
 override fun onCreate(b:Bundle?){super.onCreate(b);client=NotsipClient(this);requestPermissionsIfNeeded()
  val url=EditText(this);url.hint="NOTSIP server URL";url.setText(client.baseUrl());val id=EditText(this);id.hint="Device ID";id.setText(client.deviceId());val code=EditText(this);code.hint="Pairing code"
  val status=TextView(this);status.text="NOTSIP Android companion 0.9";val pair=Button(this);pair.text="Pair";val access=Button(this);access.text="Enable Accessibility";val mic=Button(this);mic.text="Start voice";val cam=Button(this);cam.text="Capture perception"
  val box=LinearLayout(this);box.orientation=LinearLayout.VERTICAL;box.setPadding(32,32,32,32);listOf(url,id,code,pair,access,mic,cam,status).forEach(box::addView);setContentView(box)
  pair.setOnClickListener{client.setBaseUrl(url.text.toString());client.setDeviceId(id.text.toString());scope.launch(Dispatchers.IO){try{client.pair(code.text.toString());withContext(Dispatchers.Main){status.text="Paired; bridge active";startService(Intent(this@MainActivity,NotsipCommandService::class.java))}}catch(e:Exception){withContext(Dispatchers.Main){status.text="Pairing failed: ${e.message}"}}}}
  access.setOnClickListener{startActivity(Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS))}
  mic.setOnClickListener{if(recorder==null){startRecording();mic.text="Stop voice";status.text="Recording…"}else{stopRecording();mic.text="Start voice"}}
  cam.setOnClickListener{capturePerception{status.text=it}}
 }
 private fun requestPermissionsIfNeeded(){val req= mutableListOf<String>();if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)req+=Manifest.permission.RECORD_AUDIO;if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)req+=Manifest.permission.CAMERA;if(req.isNotEmpty())requestPermissions(req.toTypedArray(),41)}
 private fun startRecording(){recordingPath=filesDir.resolve("notsip-${System.currentTimeMillis()}.m4a").absolutePath;val r=MediaRecorder();r.setAudioSource(MediaRecorder.AudioSource.MIC);r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);r.setOutputFile(recordingPath);r.prepare();r.start();recorder=r}
 private fun stopRecording(){val r=recorder?:return;try{r.stop()}catch(_:Exception){};r.release();recorder=null;scope.launch(Dispatchers.IO){try{val d=client.transcribe(java.io.File(recordingPath).readBytes());withContext(Dispatchers.Main){Toast.makeText(this@MainActivity,d.optString("text"),Toast.LENGTH_LONG).show()}}catch(e:Exception){withContext(Dispatchers.Main){Toast.makeText(this@MainActivity,"Voice error: ${e.message}",Toast.LENGTH_LONG).show()}}}}
 private fun capturePerception(done:(String)->Unit){if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){done("Camera permission required");return};startActivityForResult(Intent(MediaStore.ACTION_IMAGE_CAPTURE),77)}
 override fun onActivityResult(req:Int,res:Int,data:Intent?){super.onActivityResult(req,res,data);if(req!=77||res!=RESULT_OK)return;val bmp=data?.extras?.get("data") as? Bitmap ?: return;val out=ByteArrayOutputStream();bmp.compress(Bitmap.CompressFormat.JPEG,80,out);scope.launch(Dispatchers.IO){try{val d=client.perceive(out.toByteArray());withContext(Dispatchers.Main){Toast.makeText(this@MainActivity,d.optString("observation"),Toast.LENGTH_LONG).show()}}catch(e:Exception){withContext(Dispatchers.Main){Toast.makeText(this@MainActivity,"Vision error: ${e.message}",Toast.LENGTH_LONG).show()}}}}
 override fun onDestroy(){scope.cancel();recorder?.release();recorder=null;super.onDestroy()}
}
