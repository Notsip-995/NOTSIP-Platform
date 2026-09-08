from notsip.actor_context import set_actor,reset_actor
from notsip.store import Store
from notsip.world import WorldModel


def test_world_snapshot_filters_owned_entities_and_facts(tmp_path):
    store=Store(tmp_path);world=WorldModel(store)
    ta=set_actor('actor:a')
    try:
        world.upsert('private:a','person','Alice',{'detail':'private'},owner='actor:a')
        world.upsert('private:b','person','Bob',{'detail':'private'},owner='actor:b')
        store.fact('Alice secret','personal','',0.9,{'owner':'actor:a'})
        store.fact('Global headline','news','',0.5,{})
    finally:reset_actor(ta)
    ta=set_actor('actor:a')
    try:
        snap=world.snapshot();ids={x['id'] for x in snap['entities']};statements={x['statement'] for x in snap['facts']}
        assert 'private:a' in ids and 'private:b' not in ids
        assert 'Alice secret' in statements and 'Global headline' in statements
    finally:reset_actor(ta)
    tb=set_actor('actor:b')
    try:
        snap=world.snapshot();ids={x['id'] for x in snap['entities']};statements={x['statement'] for x in snap['facts']}
        assert 'private:a' not in ids and 'private:b' in ids
        assert 'Alice secret' not in statements and 'Global headline' in statements
    finally:reset_actor(tb)
