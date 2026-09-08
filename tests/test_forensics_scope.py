from pathlib import Path


def test_forensics_uses_actor_workspace(tmp_path):
    from notsip.forensics_scope_hardening import attach
    from notsip.actor_context import set_actor, reset_actor
    from fastapi import FastAPI

    app = FastAPI()
    class Auth:
        pass
    async def require_auth():
        return None
    attach(app, require_auth, tmp_path)
    token = set_actor('https://issuer.example/tenant:actor-a')
    try:
        manager = Path(tmp_path) / 'workspace'
        from notsip.actor_workspace import ActorWorkspace
        a = ActorWorkspace(manager).for_actor('https://issuer.example/tenant:actor-a')
        b = ActorWorkspace(manager).for_actor('https://issuer.example/tenant:actor-b')
        a.write('private.txt','A')
        b.write('private.txt','B')
        from notsip.forensics import Forensics
        assert [x['path'] for x in Forensics(a.root).scan()['files']] == ['private.txt']
        assert [x['path'] for x in Forensics(b.root).scan()['files']] == ['private.txt']
    finally:
        reset_actor(token)
