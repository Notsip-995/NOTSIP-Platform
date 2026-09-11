

def test_threat_assessment_is_evidence_first():
    from notsip.threat_assessment import ThreatAssessor
    result = ThreatAssessor().assess([
        {'type':'auth-failure','severity':'HIGH','confidence':0.9,'source':'auth'},
        {'type':'device-anomaly','severity':'HIGH','confidence':0.9,'source':'device'},
    ])
    assert result['severity'] == 'CRITICAL'
    assert result['containment_executed'] is False
    assert result['assessment'] == 'HIGH_CONFIDENCE_ASSESSMENT'


def test_threat_assessment_does_not_treat_unobserved_data_as_evidence():
    from notsip.threat_assessment import ThreatAssessor
    result = ThreatAssessor().assess([
        {'type':'unverified-signal','severity':'CRITICAL','confidence':1.0,'observed':False},
    ])
    assert result['severity'] == 'LOW'
    assert result['score'] == 0.0
