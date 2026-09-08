from notsip.event_priority import EventPriorityEngine
from notsip.event_reasoning_loop import EventReasoningLoop
from notsip.events import Event,EventBus
from notsip.jobs import Scheduler
from notsip.store import Store
import asyncio


def test_high_priority_event_creates_idempotent_review_task(tmp_path):
    store=Store(tmp_path);events=EventBus();jobs=Scheduler(store);loop=EventReasoningLoop(events,jobs,EventPriorityEngine()).attach()
    result=loop.handle(Event('health.warning',{'importance':.9,'urgency':.9,'relevance':.9},'health'))
    assert result['status']=='CREATED'
    again=loop.handle(Event('health.warning',{'importance':.9,'urgency':.9,'relevance':.9},'health'))
    assert again['task_id']==result['task_id']
    assert len(store.tasks())==1


def test_low_priority_event_is_ignored(tmp_path):
    store=Store(tmp_path);loop=EventReasoningLoop(EventBus(),Scheduler(store))
    result=loop.handle(Event('perception.observed',{'importance':.1,'urgency':.1,'relevance':.1},'vision'))
    assert result['status']=='IGNORED'
    assert store.tasks()==[]
