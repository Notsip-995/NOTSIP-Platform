from notsip.user_profile import UserProfileStore


def test_user_profile_persists_and_is_separate_from_memory(tmp_path):
    p=UserProfileStore(tmp_path,'u1')
    p.update(preferred_name='Dan',communication_style='concise')
    p.set_preference('tone','direct')
    p.add_person('Sarah',{'role':'partner'})
    again=UserProfileStore(tmp_path,'u1').load()
    assert again['preferred_name']=='Dan'
    assert again['preferences']['tone']=='direct'
    assert again['important_people']['Sarah']['role']=='partner'


def test_user_profiles_are_isolated_by_user_id(tmp_path):
    UserProfileStore(tmp_path,'alice').update(preferred_name='Alice')
    assert UserProfileStore(tmp_path,'bob').load()['preferred_name']==''
