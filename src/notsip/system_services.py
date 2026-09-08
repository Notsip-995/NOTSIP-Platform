from __future__ import annotations
import json, os, platform, shutil, socket, subprocess, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException
from .config import settings
from .tools import Workspace, Registry, Tool
from .policy import Risk


def _time_snapshot():
    now=datetime.now(ZoneInfo(settings.local_timezone));utc=datetime.now(timezone.utc)
    return {'iso':now.isoformat(),'date':now.date().isoformat(),'time':now.time().isoformat(timespec='seconds'),'timezone':settings.local_timezone,'unix':time.time(),'utc':utc.isoformat(timespec='seconds').replace('+00:00','Z')}


def _telemetry():
    disk=shutil.disk_usage(Path(settings.data_dir).resolve());out={'host':socket.gethostname(),'platform':platform.platform(),'python':platform.python_version(),'cpu_count':os.cpu_count(),'disk':{'total':disk.total,'used':disk.used,'free':disk.free},'timestamp':time.time()}
    try:
        import psutil
        vm=psutil.virtual_memory();out['memory']={'total':vm.total,'available':vm.available,'used':vm.used,'percent':vm.percent};out['cpu_percent']=psutil.cpu_percent(interval=0.1);out['boot_time']=psutil.boot_time();out['net']={name:{'is_up':stats.isup,'speed':stats.speed,'mtu':stats.mtu} for name,stats in psutil.net_if_stats().items()};battery=psutil.sensors_battery();out['battery']=None if battery is None else {'percent':battery.percent,'plugged':battery.power_plugged}
    except Exception as exc:out['metrics_note']=f'extended psutil metrics unavailable: {exc}'
    return out

class WorkflowEngine:
    def __init__(self,store,agent):self.store=store;self.agent=agent
    async def run(self,steps):
        results=[]
        for index,step in enumerate(steps):
            objective=str(step.get('objective','')).strip()
            if not objective:results.append({'index':index,'status':'FAILURE','error':'empty workflow step'});break
            result=await self.agent.handle(objective);results.append({'index':index,'objective':objective,'result':result})
            if result.get('status')=='UNKNOWN':break
        return {'status':'SUCCESS' if all(r.get('result',{}).get('status') in {'SUCCESS','DEGRADED'} for r in results) else 'PARTIAL_SUCCESS','steps':results}

def attach(app,require_auth,settings_obj,store,agent,registry):
    workspace=Workspace(Path(settings_obj.data_dir).resolve()/'workspace');workflow=WorkflowEngine(store,agent)
    def register(name,desc,capability,risk,schema,fn,destructive=False):
        if registry.get(name) is None:registry.add(Tool(name,desc,capability,risk,schema,fn,destructive))
    register('current_time','Return current local time and date.','TIME',Risk.LOW,{'type':'object','properties':{}},lambda:_time_snapshot())
    register('system_telemetry','Return host, CPU, memory, disk, network and battery telemetry when available.','SYSTEM_DIAGNOSTICS',Risk.LOW,{'type':'object','properties':{}},lambda:_telemetry())
    register('file_rename','Rename an authorized workspace file.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'source':{'type':'string'},'target':{'type':'string'}},'required':['source','target']},lambda source,target:{'status':'SUCCESS','path':str(workspace.path(source).rename(workspace.path(target)) or workspace.path(target).relative_to(workspace.root))})
    register('file_copy','Copy an authorized workspace file.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'source':{'type':'string'},'target':{'type':'string'}},'required':['source','target']},lambda source,target:_copy(workspace,source,target))
    register('file_move','Move an authorized workspace file.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'source':{'type':'string'},'target':{'type':'string'}},'required':['source','target']},lambda source,target:_move(workspace,source,target))
    register('file_delete','Delete an authorized workspace file.','WRITE_FILES',Risk.HIGH,{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},lambda path:_delete(workspace,path),True)
    register('file_archive','Create a ZIP archive of authorized workspace paths.','WRITE_FILES',Risk.MEDIUM,{'type':'object','properties':{'paths':{'type':'array','items':{'type':'string'}},'archive':{'type':'string'}},'required':['paths','archive']},lambda paths,archive:_archive(workspace,paths,archive))
    register('python_exec','Run code in an isolated sandbox; requires approval.','CODE_EXECUTION',Risk.HIGH,{'type':'object','properties':{'code':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':60}},'required':['code']},lambda code,timeout=30:_python_exec(workspace,code,timeout),True)
    register('simulate','Run a deterministic numeric simulation in an isolated sandbox; requires approval.','SIMULATION',Risk.HIGH,{'type':'object','properties':{'code':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':60}},'required':['code']},lambda code,timeout=30:_python_exec(workspace,code,timeout),True)
    @app.get('/api/time')
    async def current_time(_:None=Depends(require_auth)):return _time_snapshot()
    @app.get('/api/telemetry')
    async def telemetry(_:None=Depends(require_auth)):return _telemetry()
    @app.post('/api/files/rename')
    async def file_rename(payload:dict,_:None=Depends(require_auth)):return _rename(workspace,str(payload.get('source','')),str(payload.get('target','')))
    @app.post('/api/files/copy')
    async def file_copy(payload:dict,_:None=Depends(require_auth)):return _copy(workspace,str(payload.get('source','')),str(payload.get('target','')))
    @app.post('/api/files/move')
    async def file_move(payload:dict,_:None=Depends(require_auth)):return _move(workspace,str(payload.get('source','')),str(payload.get('target','')))
    @app.post('/api/files/delete')
    async def file_delete(payload:dict,_:None=Depends(require_auth)):return _delete(workspace,str(payload.get('path','')))
    @app.post('/api/files/archive')
    async def file_archive(payload:dict,_:None=Depends(require_auth)):return _archive(workspace,list(payload.get('paths') or []),str(payload.get('archive','')))
    @app.post('/api/workflows/run')
    async def workflow_run(payload:dict,_:None=Depends(require_auth)):
        steps=payload.get('steps') or []
        if not isinstance(steps,list) or not steps:raise HTTPException(400,'workflow steps required')
        if len(steps)>50:raise HTTPException(400,'workflow too large')
        return await workflow.run(steps)

def _rename(workspace,source,target):
    src=workspace.path(source);dst=workspace.path(target);dst.parent.mkdir(parents=True,exist_ok=True);src.rename(dst);return {'status':'SUCCESS','path':str(dst.relative_to(workspace.root))}

def _copy(workspace,source,target):
    src=workspace.path(source);dst=workspace.path(target);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);return {'status':'SUCCESS','path':str(dst.relative_to(workspace.root)),'bytes':dst.stat().st_size}

def _move(workspace,source,target):return _rename(workspace,source,target)

def _delete(workspace,path):
    p=workspace.path(path)
    if not p.exists():raise FileNotFoundError(path)
    if p.is_dir():shutil.rmtree(p)
    else:p.unlink()
    return {'status':'SUCCESS','deleted':path}

def _archive(workspace,paths,archive):
    ap=workspace.path(archive);ap.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ap,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in paths:
            p=workspace.path(rel)
            if p.is_dir():
                for f in p.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(workspace.root).as_posix())
            elif p.is_file():z.write(p,p.relative_to(workspace.root).as_posix())
            else:raise FileNotFoundError(rel)
    return {'status':'SUCCESS','archive':str(ap.relative_to(workspace.root)),'bytes':ap.stat().st_size}

def _python_exec(workspace,code,timeout=30):
    p=workspace.root/'runtime_exec';p.mkdir(parents=True,exist_ok=True);script=p/'run.py';script.write_text(code,encoding='utf-8')
    try:
        mode=os.getenv('NOTSIP_CODE_SANDBOX','disabled').strip().lower();timeout=max(1,min(int(timeout),60))
        if mode=='docker':
            docker=shutil.which('docker')
            if not docker:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'Docker sandbox runtime is required but docker was not found'}
            image=os.getenv('NOTSIP_CODE_SANDBOX_IMAGE','python:3.12-slim');cmd=[docker,'run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','512m','--cpus','1','--tmpfs','/tmp:rw,size=64m','-v',f'{workspace.root.resolve()}:/workspace:rw','-w','/workspace',image,'python','-I','/workspace/runtime_exec/run.py']
        elif mode=='local-unsafe' and os.getenv('NOTSIP_ALLOW_UNSAFE_CODE_EXEC','').lower() in {'1','true','yes'}:cmd=[os.environ.get('PYTHON','python'),'-I',str(script)]
        else:return {'status':'BLOCKED_BY_EXTERNAL_ENVIRONMENT','error':'isolated code sandbox is not configured; set NOTSIP_CODE_SANDBOX=docker with Docker available'}
        r=subprocess.run(cmd,cwd=str(workspace.root),capture_output=True,text=True,timeout=timeout);return {'status':'SUCCESS' if r.returncode==0 else 'FAILURE','returncode':r.returncode,'stdout':r.stdout[-20000:],'stderr':r.stderr[-20000:]}
    finally:script.unlink(missing_ok=True)
