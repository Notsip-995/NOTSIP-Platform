from notsip.forensics import Forensics


def test_forensics_investigation_returns_evidence_and_verification_boundary(tmp_path):
    p=tmp_path/'download-temp';p.mkdir();f=p/'payload.ps1';f.write_text('Write-Output hello',encoding='utf-8')
    result=Forensics(tmp_path).investigate()
    assert result['status']=='SUCCESS'
    assert result['collection']['files']==1
    assert result['hypotheses']
    assert result['verification']['status']=='NOT_PERFORMED'
    assert len(result['report']['evidence_hash'])==64
