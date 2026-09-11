import asyncio
from notsip.store import Store
from notsip.system_services import WorkflowEngine

class AgentStub:
    async def handle(self,objective):
        if objective=='fail':return {'status':'FAILURE','error':'boom'}
        return {'status':'SUCCESS','response':objective}


def test_workflow_honors_dependencies_and_conditions(tmp_path):
    workflow=WorkflowEngine(Store(tmp_path),AgentStub())
    result=asyncio.run(workflow.run([
        {'id':'a','objective':'first'},
        {'id':'b','objective':'fail','depends_on':['a']},
        {'id':'c','objective':'never','depends_on':['b'],'condition':'on_success'},
        {'id':'d','objective':'recover','depends_on':['b'],'condition':'on_failure'},
    ]))
    by_id={x['id']:x for x in result['steps']}
    assert by_id['a']['status']=='SUCCESS'
    assert by_id['b']['status']=='FAILURE'
    assert by_id['c']['status']=='SKIPPED'
    assert by_id['d']['status']=='SUCCESS'


def test_workflow_rejects_dependency_cycle(tmp_path):
    workflow=WorkflowEngine(Store(tmp_path),AgentStub())
    result=asyncio.run(workflow.run([{'id':'a','objective':'x','depends_on':['b']},{'id':'b','objective':'y','depends_on':['a']}]))
    assert result['status']=='FAILURE'
    assert 'cycle' in result['error']
