from notsip.event_priority import EventPriorityEngine, Priority
from notsip.predictive_maintenance import PredictiveMaintenance
from notsip.task_decomposer import TaskDecomposer


def test_event_priority_suppresses_trivial_interrupts():
    d=EventPriorityEngine().classify(importance=.1,urgency=.0,relevance=.1,event_type='background')
    assert d.priority in {Priority.IGNORE,Priority.BACKGROUND}
    assert d.interrupt is False


def test_event_priority_allows_important_interrupt():
    d=EventPriorityEngine().classify(importance=.8,urgency=.8,relevance=.9,event_type='calendar.event.starting')
    assert d.priority in {Priority.IMPORTANT,Priority.URGENT,Priority.CRITICAL}
    assert d.interrupt is True


def test_predictive_maintenance_labels_prediction():
    p=PredictiveMaintenance();r=p.evaluate([{'cpu':50},{'cpu':60},{'cpu':80}], 'cpu', warning_slope=.1, failure_threshold=100)
    assert r['status']=='SUCCESS'
    assert r['prediction']['is_prediction'] is True
    assert r['trend']['slope_per_sample'] > 0


def test_predictive_maintenance_unknown_without_data():
    r=PredictiveMaintenance().evaluate([], 'temperature')
    assert r['status']=='UNKNOWN'


def test_task_decomposer_builds_dependencies():
    plan=TaskDecomposer().decompose('Prepare me for tomorrow meeting and review the report')
    assert plan['status']=='SUCCESS'
    assert len(plan['subtasks']) >= 2
    assert any(item['dependencies'] for item in plan['subtasks'])
