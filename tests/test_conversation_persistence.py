from notsip.conversations import ConversationStore

def test_latest_session_restored_after_restart(tmp_path):
    first = ConversationStore(tmp_path, 'primary-user')
    created = first.get_or_create()
    first.append(created['id'], 'user', 'remember this')
    second = ConversationStore(tmp_path, 'primary-user')
    restored = second.get_or_create()
    assert restored['id'] == created['id']
    assert second.history(restored['id'], 10)[-1]['content'] == 'remember this'
