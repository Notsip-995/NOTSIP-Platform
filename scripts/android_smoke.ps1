$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$apk='android/app/build/outputs/apk/debug/app-debug.apk'
if(-not(Test-Path $apk)){throw 'Build Android APK first.'}
$devices=& adb devices | Select-String "device$"
if(-not $devices){throw 'No authorized Android device found through adb.'}
& adb install -r $apk | Write-Host
& adb shell am force-stop com.notsip.mobile
& adb shell monkey -p com.notsip.mobile 1 | Write-Host
Start-Sleep -Seconds 2
$pkg=& adb shell dumpsys package com.notsip.mobile
if(-not($pkg -match 'Package \[com\.notsip\.mobile\]')){throw 'NOTSIP Android package is not installed.'}
Write-Host 'Android package launch smoke test passed.' -ForegroundColor Green
