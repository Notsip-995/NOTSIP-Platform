from notsip.task_decomposer import TaskDecomposer


def test_complex_goal_produces_durable_subtasks():
    plan=TaskDecomposer().decompose('prepare a report about the server incident')
    assert plan['status']=='SUCCESS'
    assert len(plan['subtasks'])>=3
    assert plan['completion_condition']=='all required subtasks have verified outcomes'
    assert TaskDecomposer().critical_path(plan)==[1]


def test_simple_goal_still_has_understand_execute_verify_chain():
    plan=TaskDecomposer().decompose('organize my files')
    categories=[x['category'] for x in plan['subtasks']]
    assert categories==['understanding','execution','verification']
