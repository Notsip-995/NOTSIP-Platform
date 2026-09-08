

def test_workflow_handler_is_registered():
    from notsip.core_runtime import jobs
    assert 'workflow' in jobs.handlers


def test_workflow_handler_uses_canonical_engine():
    from notsip.workflow_runtime_hardening import attach
    from notsip.system_services import WorkflowEngine
    class Jobs:
        def __init__(self): self.handlers = {}
        def register(self, name, fn): self.handlers[name] = fn
    class Store: pass
    class Agent: pass
    jobs = Jobs()
    engine = attach(jobs, Store(), Agent())
    assert isinstance(engine, WorkflowEngine)
    assert 'workflow' in jobs.handlers
