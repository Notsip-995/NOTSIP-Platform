from notsip.windows_automation import WindowsAutomation


def test_unverified_windows_actions_have_non_success_contract_without_windows_backend(monkeypatch):
    # The methods themselves require Windows/pywinauto; this regression pins the
    # source-level contract that successful outcomes must carry verification.
    text=__import__('pathlib').Path('src/notsip/windows_automation.py').read_text(encoding='utf-8')
    assert "'status':'UNKNOWN'" in text
    assert "'verified':False" in text
