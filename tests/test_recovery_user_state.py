import json
from pathlib import Path
from notsip.recovery_state_hardening import capture,restore
from notsip.conversations import ConversationStore
from notsip.user_profile import UserProfileStore


def test_user_state_round_trip(tmp_path):
    conversations=ConversationStore(tmp_path,'issuer:user-a')
    session=conversations.create('Project A');conversations.append(session['id'],'user','hello')
    profile=UserProfileStore(tmp_path,'issuer:user-a');profile.update(preferred_name='Alice')
    snapshot=capture(tmp_path)
    conversations.path.unlink();profile.path.unlink()
    result=restore(tmp_path,snapshot)
    assert 'runtime/conversations.json' in result['restored_files']
    assert ConversationStore(tmp_path,'issuer:user-a').history(session['id'],10)[0]['content']=='hello'
    assert UserProfileStore(tmp_path,'issuer:user-a').load()['preferred_name']=='Alice'


def test_user_state_rejects_unsafe_filename(tmp_path):
    try:restore(tmp_path,{'../escape.json':{}})
    except ValueError as exc:assert 'unsupported recovery user-state file' in str(exc)
    else:raise AssertionError('unsafe recovery filename was accepted')
