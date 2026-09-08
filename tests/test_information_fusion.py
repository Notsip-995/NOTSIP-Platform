from notsip.information_fusion import InformationFusion

class Store:
    def facts(self,limit):
        return [
            {'statement':'Server capacity increased','source':'ops-a','url':'a','confidence':0.8,'retrieved':1,'metadata':{'subject':'server capacity','originality':1.0,'corroboration':1}},
            {'statement':'Server capacity decreased','source':'ops-b','url':'b','confidence':0.7,'retrieved':2,'metadata':{'subject':'server capacity','originality':1.0,'corroboration':0}},
        ]

class Web:
    enabled=False


def test_fusion_preserves_originality_and_corroboration():
    result=__import__('asyncio').run(InformationFusion(Store(),Web()).fuse('server'))
    assert all('originality' in e and 'corroboration' in e for e in result['evidence'])
    assert all('originality' in c and 'corroboration' in c for c in result['claims'])


def test_fusion_reports_explicit_conflicts_instead_of_collapsing_them():
    result=__import__('asyncio').run(InformationFusion(Store(),Web()).fuse('server'))
    assert result['conflicts'] and result['conflicts'][0]['status']=='CONFLICTING_EVIDENCE'
    assert len(result['conflicts'][0]['statements'])==2
