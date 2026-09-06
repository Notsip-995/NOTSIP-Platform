package com.notsip.mobile
import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
class NotsipAccessibilityService:AccessibilityService(){init{NotsipAccessibilityServiceHolder.instance=this};override fun onAccessibilityEvent(event:AccessibilityEvent?){};override fun onInterrupt(){};fun clickText(text:String)=rootInActiveWindow?.let{find(it,text)}?:false;private fun find(n:AccessibilityNodeInfo,text:String):Boolean{for(i in 0 until n.childCount){val c=n.getChild(i)?:continue;if(c.text?.toString()==text&&c.isClickable){c.performAction(AccessibilityNodeInfo.ACTION_CLICK);return true};if(find(c,text))return true};return false}}
object NotsipAccessibilityServiceHolder{var instance:NotsipAccessibilityService?=null}
