import json
import pytest
from notsip.communication_service import CommunicationService
from notsip.store import Store
from notsip.user_profile import UserProfileStore


def test_sms_resolves_known_contact_and_queues_on_online_android(tmp_path):
    profile=UserProfileStore(tmp_path);profile.add_person('Sarah',{'phone':'+250788123456'})
    store=Store(tmp_path);store.pair_device('android-1','Phone','android','', 'token')
    service=CommunicationService(profile,store)
    result=service.sms('Sarah','I am ten minutes late.')
    assert result['status']=='QUEUED' and result['channel']=='sms' and result['verified'] is False
    row=store.row('SELECT device_id,action,payload,status FROM commands WHERE id=?',(result['command_id'],))
    assert row and row['device_id']=='android-1' and row['action']=='send_sms' and row['status']=='PENDING'
    assert json.loads(row['payload'])['number']=='+250788123456'


def test_sms_fails_for_unknown_contact(tmp_path):
    service=CommunicationService(UserProfileStore(tmp_path),Store(tmp_path))
    with pytest.raises(LookupError):service.sms('Unknown','hello')


def test_sms_fails_closed_without_online_android(tmp_path):
    profile=UserProfileStore(tmp_path);profile.add_person('Sarah',{'phone':'+250788123456'})
    with pytest.raises(RuntimeError,match='no online authorized Android'):
        CommunicationService(profile,Store(tmp_path)).sms('Sarah','hello')


def test_sms_rejects_malformed_phone(tmp_path):
    profile=UserProfileStore(tmp_path);profile.add_person('Sarah',{'phone':'not-a-phone'})
    store=Store(tmp_path);store.pair_device('android-1','Phone','android','', 'token')
    with pytest.raises(ValueError,match='invalid format'):
        CommunicationService(profile,store).sms('Sarah','hello')
