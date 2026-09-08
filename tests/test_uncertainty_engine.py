from notsip.uncertainty_engine import UncertaintyEngine


def test_uncertainty_blocks_without_authorization():
    r=UncertaintyEngine().evaluate(evidence_count=5,confidence=.9,authorized=False)
    assert r.status=='BLOCKED'
    assert 'authorization missing' in r.reasons


def test_uncertainty_identifies_conflicting_low_confidence_evidence():
    r=UncertaintyEngine().evaluate(evidence_count=3,confidence=.4,conflicts=1,authorized=True)
    assert r.status=='UNCERTAIN'
    assert r.action


def test_uncertainty_requires_confirmation_for_irreversible_high_confidence_action():
    r=UncertaintyEngine().evaluate(evidence_count=5,confidence=.95,conflicts=0,authorized=True,reversible=False)
    assert r.status=='HIGH_CONFIDENCE'
    assert 'explicit confirmation' in r.action
