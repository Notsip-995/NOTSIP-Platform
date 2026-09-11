import asyncio,json,time
from notsip.distributed_failover import attach
from notsip.events import Event,EventBus
from notsip.store import Store


def test_pending_node_task_is_redispatched(tmp_path):
    store=Store(tmp_path)
    tid=store.task('node work',data={'target_node':'node-a','actor':'issuer:user-a'})
    bus=EventBus();attach(bus,store)
    asyncio.run(bus.publish(Event('nodes.stale',{'nodes':[{'id':'node-a','status':'STALE'}]},'test')))
    row=store.row('SELECT * FROM tasks WHERE id=?',(tid,))
    data=json.loads(row['data'])
    assert row['state']=='PENDING'
    assert data['redispatched_without_node'] is True
    assert 'target_node' not in data


def test_running_node_task_becomes_unknown(tmp_path):
    store=Store(tmp_path)
    tid=store.task('node work',state='RUNNING',data={'target_node':'node-a'})
    bus=EventBus();attach(bus,store)
    asyncio.run(bus.publish(Event('nodes.stale',{'nodes':[{'id':'node-a','status':'STALE'}]},'test')))
    row=store.row('SELECT * FROM tasks WHERE id=?',(tid,))
    assert row['state']=='UNKNOWN'
    assert 'manual reconciliation' in row['error']


def test_stale_event_is_idempotent(tmp_path):
    store=Store(tmp_path);tid=store.task('node work',data={'target_node':'node-a'});bus=EventBus();attach(bus,store)
    event=Event('nodes.stale',{'nodes':[{'id':'node-a','status':'STALE'}]},'test')
    asyncio.run(bus.publish(event));asyncio.run(bus.publish(event))
    row=store.row('SELECT * FROM tasks WHERE id=?',(tid,));assert row['state']=='PENDING'
