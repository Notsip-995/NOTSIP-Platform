from pathlib import Path
import pytest

from notsip.product_layer import ApprovalStore, AuditLog


def test_corrupt_approval_store_is_not_treated_as_empty(tmp_path):
    path=Path(tmp_path)/'runtime'/'approvals.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{not-json',encoding='utf-8')
    with pytest.raises(RuntimeError,match='approval store is corrupt'):
        ApprovalStore(tmp_path)._load()


def test_corrupt_audit_tail_blocks_new_entries(tmp_path):
    path=Path(tmp_path)/'runtime'/'audit.jsonl';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{not-json\n',encoding='utf-8')
    log=AuditLog(tmp_path)
    with pytest.raises(RuntimeError,match='audit log is corrupt'):
        log.write('after-corruption')
