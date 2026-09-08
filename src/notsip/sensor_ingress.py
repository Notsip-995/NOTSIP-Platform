from __future__ import annotations
import math,time
from fastapi import Header,HTTPException,Request
from .events import Event

_ALLOWED={'temperature','humidity','motion','light','location','network_status','device_status','power','battery','vehicle_status','security_sensor','camera_observation','microphone_observation','custom'}


def attach(app,store,world,events):
    @app.post('/api/sensors/report')
    async def sensor_report(payload:dict,request:Request,x_notsip_device_id:str=Header('',alias='X-NOTSIP-Device-ID'),x_notsip_device_token:str=Header('',alias='X-NOTSIP-Device-Token')):
        device_id=x_notsip_device_id.strip();token=x_notsip_device_token
        if not device_id or not token or not store.device_token_valid(device_id,token):raise HTTPException(401,'device authentication required')
        device=store.row('SELECT id,name,platform,status FROM devices WHERE id=?',(device_id,))
        if not device or device.get('status') in {'REVOKED','REPAIR_REQUIRED'}:raise HTTPException(403,'device is not authorized for sensor reporting')
        sensor_type=str(payload.get('sensor_type','')).strip().lower();
        if sensor_type not in _ALLOWED:raise HTTPException(400,f'unsupported sensor_type: {sensor_type}')
        observed=float(payload.get('observed_at',time.time()) or time.time())
        if not math.isfinite(observed) or observed>time.time()+300:raise HTTPException(400,'invalid or implausibly future observed_at')
        value=payload.get('value');
        if value is None:raise HTTPException(400,'sensor value is required')
        metadata=payload.get('metadata') or {}
        if not isinstance(metadata,dict):raise HTTPException(400,'metadata must be an object')
        entity_id=f'device:{device_id}:sensor:{sensor_type}'
        observation={'device_id':device_id,'device_name':device.get('name',''),'sensor_type':sensor_type,'value':value,'unit':str(payload.get('unit','')),'observed_at':observed,'metadata':metadata}
        world.upsert(entity_id,'sensor',sensor_type,{'device_id':device_id,'reading':observation})
        store.fact(f'{sensor_type} reading from {device_id}: {value}',f'device:{device_id}',metadata.get('source_url',''),.8,observation)
        await events.publish(Event(f'sensor.{sensor_type}',observation,f'device:{device_id}'))
        await events.publish(Event('sensor.reading',observation,f'device:{device_id}'))
        return {'status':'SUCCESS','verified':True,'reading':observation,'world_entity':entity_id}
