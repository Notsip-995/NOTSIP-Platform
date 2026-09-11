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


def test_completed_feedback_task_creates_bounded_evaluation(tmp_path):
    store=Store(tmp_path);jobs=Scheduler(store);events=EventBus();loop=EventReasoningLoop(events,jobs).attach()
    result=loop.handle(Event('task.completed',{
        'task_id':'task-1','execution_id':'exec-1','objective':'Collect telemetry',
        'result':{'status':'SUCCESS','verified':True},
        'task_data':{'requester':'primary-user','priority':2,'feedback_loop':{'enabled':True,'max_cycles':2,'guidance':{'next':'recheck'}}}
    },'scheduler'))
    assert result['status']=='CREATED' and result['cycle']==1
    tasks=store.tasks();assert len(tasks)==1
    data=__import__('json').loads(tasks[0]['data']);assert data['review_only'] is True and data['feedback_cycle']==1


def test_feedback_does_not_recurse_on_review_task_completion(tmp_path):
    store=Store(tmp_path);jobs=Scheduler(store);events=EventBus();loop=EventReasoningLoop(events,jobs).attach()
    result=loop.handle(Event('task.completed',{
        'task_id':'review-1','execution_id':'exec-review','objective':'Evaluate outcome',
        'result':{'status':'SUCCESS'},
        'task_data':{'review_only':True,'feedback_loop':{'enabled':True,'max_cycles':2}}
    },'scheduler'))
    assert result['status']=='IGNORED'
    assert store.tasks()==[]


def test_feedback_stops_at_cycle_limit(tmp_path):
    store=Store(tmp_path);jobs=Scheduler(store);loop=EventReasoningLoop(EventBus(),jobs)
    result=loop.handle(Event('task.failed',{
        'task_id':'task-2','execution_id':'exec-2','objective':'Do thing','error':'nope',
        'task_data':{'feedback_loop':{'enabled':True,'max_cycles':1},'feedback_cycle':1}
    },'scheduler'))
    assert result['status']=='STOPPED'
    assert store.tasks()==[]
