from notsip.intelligence import Intelligence
from notsip.store import Store
from notsip.world import WorldModel
from notsip.actor_context import set_actor,reset_actor


def test_trigger_candidates_are_actor_scoped(tmp_path):
    store=Store(tmp_path);world=WorldModel(store);intel=Intelligence(store,world)
    store.remember('issuer:user-a','semantic','todo: review project A',.95)
    store.remember('issuer:user-b','semantic','todo: review project B',.95)
    ta=set_actor('issuer:user-a')
    try:a=intel.trigger_candidates()
    finally:reset_actor(ta)
    tb=set_actor('issuer:user-b')
    try:b=intel.trigger_candidates()
    finally:reset_actor(tb)
    assert [x['memory'] for x in a]==['todo: review project A']
    assert [x['memory'] for x in b]==['todo: review project B']
