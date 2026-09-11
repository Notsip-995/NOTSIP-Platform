

def test_non_primary_actor_profile_path_is_safely_namespaced(tmp_path):
    from notsip.user_profile import UserProfileStore
    store = UserProfileStore(tmp_path, 'https://issuer.example/tenant:subject')
    assert store.path.parent == (tmp_path / 'profiles').resolve()
    assert '/' not in store.path.name
    assert ':' not in store.path.name


def test_primary_profile_path_remains_stable(tmp_path):
    from notsip.user_profile import UserProfileStore
    store = UserProfileStore(tmp_path, 'primary-user')
    assert store.path.name == 'user-profile-primary-user.json'
