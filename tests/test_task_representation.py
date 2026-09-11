import json
import time


def test_task_payload_persists_blueprint_fields():
    from notsip.task_hardening import _task_data
    actor = 'oidc:actor-a'
    payload = {
        'context': {'project': 'alpha'},
        'deadline': time.time() + 3600,
        'constraints': ['do-not-delete'],
        'required_tools': ['search_workspace'],
        'subtasks': [{'id': 's1', 'objective': 'inspect'}],
        'verification': {'type': 'postcondition'},
        'data': {'arbitrary': 'value'},
    }
    data = _task_data(payload, actor)
    assert data['actor'] == actor
    assert data['requester'] == actor
    assert data['context']['project'] == 'alpha'
    assert data['constraints'] == ['do-not-delete']
    assert data['required_tools'] == ['search_workspace']
    assert data['subtasks'][0]['id'] == 's1'
    assert data['verification']['type'] == 'postcondition'
    assert data['arbitrary'] == 'value'


def test_task_data_is_json_serializable():
    from notsip.task_hardening import _task_data
    data = _task_data({'deadline': time.time() + 60}, 'primary-user')
    json.dumps(data)
