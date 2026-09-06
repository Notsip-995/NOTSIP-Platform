package com.notsip.mobile
import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.*
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
class MainActivity:Activity(){override fun onCreate(b:Bundle?){super.onCreate(b);val c=NotsipClient(this);val u=EditText(this);u.hint="NOTSIP server URL";u.setText(c.baseUrl());val d=EditText(this);d.hint="Device ID";d.setText(c.deviceId());val code=EditText(this);code.hint="Pairing code";val st=TextView(this);st.text="NOTSIP Android companion";val pair=Button(this);pair.text="Pair";val a=Button(this);a.text="Enable Accessibility";val r=LinearLayout(this);r.orientation=LinearLayout.VERTICAL;r.setPadding(32,32,32,32);r.addView(u);r.addView(d);r.addView(code);r.addView(pair);r.addView(a);r.addView(st);setContentView(r);pair.setOnClickListener{c.setBaseUrl(u.text.toString());c.setDeviceId(d.text.toString());lifecycleScope.launch{try{c.pair(code.text.toString());st.text="Paired and starting bridge";startService(Intent(this@MainActivity,NotsipCommandService::class.java))}catch(e:Exception){st.text="Pairing failed: ${e.message}"}}};a.setOnClickListener{startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))}}}
