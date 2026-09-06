from notsip.core_runtime import app

def test_app():
    assert app.title=='NOTSIP' and app.version=='0.8.0'
