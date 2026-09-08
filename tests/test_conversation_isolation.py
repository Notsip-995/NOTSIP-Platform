from notsip.conversations import ConversationStore


def test_conversation_store_isolates_users(tmp_path):
    alice = ConversationStore(tmp_path, user_id='alice')
    bob = ConversationStore(tmp_path, user_id='bob')
    session = alice.create('Alice private')
    alice.append(session['id'], 'user', 'secret')

    assert session['id'] not in {s['id'] for s in bob.list()}
    assert bob.history(session['id']) == []

    selected = bob.get_or_create(session['id'])
    assert selected['user_id'] == 'bob'
    assert selected['id'] != session['id']

    assert bob.summarize(session['id'], 'attacker summary') is None
    try:
        bob.append(session['id'], 'user', 'attacker message')
    except PermissionError:
        pass
    else:
        raise AssertionError('cross-user append must be rejected')
