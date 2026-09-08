from .tools import Tool
from .policy import Risk


def attach(registry, adapter):
    """Replace any satellite tool that accepts caller-supplied authorization."""
    existing=registry.get('satellite_query')
    schema={'type':'object','properties':{'bbox':{'type':'string'},'start':{'type':'string'},'end':{'type':'string'},'scene_id':{'type':'string'}},'required':['bbox','start','end']}
    if existing is None:
        registry.add(Tool('satellite_query','Query a server-authorized satellite/remote-sensing provider; caller cannot self-attest authorization.','INTERNET_SEARCH',Risk.HIGH,schema,lambda bbox,start,end,scene_id='':adapter.satellite_query(bbox,start,end,scene_id,authorized=True)))
    else:
        existing.schema=schema
        existing.risk=Risk.HIGH
        existing.destructive=False
        existing.fn=lambda bbox,start,end,scene_id='':adapter.satellite_query(bbox,start,end,scene_id,authorized=True)
    return registry
