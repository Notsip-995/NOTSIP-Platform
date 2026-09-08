import asyncio
from pathlib import Path
import pytest
from notsip.events import Event,EventBus
from notsip.notifications import NotificationStore
from notsip.notification_hardening import attach


def test_notification_isolation_and_ack(tmp_path):
    store=NotificationStore(tmp_path)
    a=store.create('issuer:user-a','Title','Private A',dedupe_key='a')
    b=store.create('issuer:user-b','Title','Private B',dedupe_key='b')
    assert [x['body'] for x in store.list('issuer:user-a')]==['Private A']
    assert [x['body'] for x in store.list('issuer:user-b')]==['Private B']
    assert store.acknowledge('issuer:user-b',a['id']) is None
    assert store.acknowledge('issuer:user-a',a['id'])['acknowledged'] is True


def test_duplicate_proactive_events_are_coalesced(tmp_path):
    store=NotificationStore(tmp_path)
    bus=EventBus();attach(type('App',(),{'router':type('R',(),{'routes':[]})()})(),bus,store,lambda request:None)
    event=Event('proactive.candidate',{'actor':'issuer:user-a','type':'follow_up','memory':'todo: review A','priority':'IMPORTANT','reason':'follow_up'},'intelligence')
    asyncio.run(bus.publish(event));asyncio.run(bus.publish(event))
    assert len(store.list('issuer:user-a',include_ack=True))==1


def test_custom_dedupe_key_cannot_cross_actor(tmp_path):
    store=NotificationStore(tmp_path)
    a=store.create('issuer:user-a','Title','A',dedupe_key='shared')
    b=store.create('issuer:user-b','Title','B',dedupe_key='shared')
    assert a['id']!=b['id']
    assert [x['body'] for x in store.list('issuer:user-a',include_ack=True)]==['A']
    assert [x['body'] for x in store.list('issuer:user-b',include_ack=True)]==['B']


def test_corrupt_notification_store_fails_closed(tmp_path):
    path=Path(tmp_path)/'runtime'/'notifications.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{not-json',encoding='utf-8')
    with pytest.raises(RuntimeError,match='notification store is corrupt'):
        NotificationStore(tmp_path).list('issuer:user-a')
