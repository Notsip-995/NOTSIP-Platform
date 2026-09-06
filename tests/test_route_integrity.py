from notsip.core_runtime import app

def test_no_duplicate_route_method_pairs():
    seen=set()
    duplicates=[]
    for route in app.routes:
        path=getattr(route,'path',None)
        methods=getattr(route,'methods',set()) or set()
        for method in methods:
            key=(method,path)
            if key in seen:duplicates.append(key)
            seen.add(key)
    assert not duplicates, f'duplicate route registrations: {duplicates}'
