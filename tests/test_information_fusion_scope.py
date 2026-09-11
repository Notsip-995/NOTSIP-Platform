from notsip.actor_context import reset_actor, set_actor


class StoreStub:
    def facts(self, n=100):
        return [
            {'statement':'private actor A', 'source':'conversation', 'metadata':{'actor':'actor-a'}, 'confidence':0.9},
            {'statement':'private actor B', 'source':'conversation', 'metadata':{'actor':'actor-b'}, 'confidence':0.9},
            {'statement':'public fact', 'source':'public', 'metadata':{}, 'confidence':0.8},
        ]

    def device_owned_by(self, device_id, owner=None):
        return False


def test_fusion_filters_private_facts_by_actor():
    from notsip.information_fusion import InformationFusion
    service = InformationFusion(StoreStub(), type('Web', (), {'enabled': False})())
    token = set_actor('actor-a')
    try:
        rows = service.stored('actor', 20)
    finally:
        reset_actor(token)
    assert [r['statement'] for r in rows] == ['private actor A']


def test_fusion_keeps_public_facts_for_secondary_actor():
    from notsip.information_fusion import InformationFusion
    service = InformationFusion(StoreStub(), type('Web', (), {'enabled': False})())
    token = set_actor('actor-c')
    try:
        rows = service.stored('fact', 20)
    finally:
        reset_actor(token)
    assert [r['statement'] for r in rows] == ['public fact']


def test_all_visible_filters_private_facts_for_secondary_actor():
    from notsip.information_fusion import InformationFusion
    service = InformationFusion(StoreStub(), type('Web', (), {'enabled': False})())
    rows = service.all_visible(20, 'actor-b')
    assert [r['statement'] for r in rows] == ['private actor B', 'public fact']


def test_intelligence_corroboration_filters_private_facts_by_actor():
    from notsip.intelligence import Intelligence
    service = Intelligence(StoreStub(), type('World', (), {'snapshot':lambda self: {'relations':[]}})())
    token = set_actor('actor-a')
    try:
        rows = service.corroborate('private')
    finally:
        reset_actor(token)
    assert [r['statement'] for r in rows] == ['private actor A']
