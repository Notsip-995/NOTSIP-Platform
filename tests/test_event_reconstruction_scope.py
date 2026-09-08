from notsip.event_reconstruction import EventReconstructor


class StoreStub:
    def audit_recent(self, n=100):
        return [
            {'user_id':'actor-a','ts':2,'tool':'tool-a','action':'run','request':'private-a','result':'ok'},
            {'user_id':'actor-b','ts':3,'tool':'tool-b','action':'run','request':'private-b','result':'ok'},
        ]


class JournalStub:
    def recent(self, limit=100):
        return [
            {'ts':1,'type':'private','source':'custom','payload':{'actor':'actor-a'}},
            {'ts':2,'type':'private','source':'custom','payload':{'actor':'actor-b'}},
            {'ts':3,'type':'system','source':'system','payload':{}},
        ]


def test_reconstruction_filters_private_events():
    result = EventReconstructor(StoreStub(), JournalStub()).reconstruct(actor='actor-a')
    payloads = [e.get('payload') for e in result['events']]
    assert any(p.get('actor') == 'actor-a' for p in payloads if isinstance(p, dict))
    assert not any(p.get('actor') == 'actor-b' for p in payloads if isinstance(p, dict))
    assert any(e.get('source') == 'audit' and e['payload'].get('user_id') == 'actor-a' for e in result['events'])
