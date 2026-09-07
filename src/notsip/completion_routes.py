from __future__ import annotations
import base64, binascii
from fastapi import Depends, File, HTTPException, UploadFile
from .events import Event


def attach(app, *, require_auth, media, maintenance, store, nodes, oauth, settings, events=None):
    @app.get('/api/config/public')
    async def config_public():
        secret_names={'api_key','event_hmac_secret','pairing_secret','llm_api_key','fallback_llm_api_key','stt_api_key','tts_api_key','email_password','oidc_client_secret','oauth_client_secret','node_shared_secret','brave_api_key','database_url'}
        values={k:getattr(settings,k) for k in settings.__class__.model_fields if k not in secret_names}
        presence={k:bool(getattr(settings,k,None)) for k in secret_names}
        return {'settings':values,'secret_configured':presence}

    @app.post('/api/voice/transcribe')
    async def voice_transcribe(file: UploadFile = File(...), language: str = '', _: None = Depends(require_auth)):
        if not settings.stt_base_url or not settings.stt_model:
            raise HTTPException(503, 'STT is not configured')
        raw = await file.read()
        if len(raw) > 30 * 1024 * 1024:
            raise HTTPException(413, 'audio file too large')
        return await media.transcribe(raw, file.content_type or 'audio/webm', language or settings.stt_language)

    @app.post('/api/voice/speak')
    async def voice_speak(payload: dict, _: None = Depends(require_auth)):
        text = str(payload.get('text', '')).strip()
        if not text:
            raise HTTPException(400, 'text is required')
        if not settings.tts_base_url or not settings.tts_model:
            raise HTTPException(503, 'TTS is not configured')
        return await media.speak(text, str(payload.get('voice') or settings.tts_voice))

    @app.post('/api/perception/frame')
    async def perception_frame(payload: dict, _: None = Depends(require_auth)):
        try:
            raw = base64.b64decode(str(payload.get('image_base64', '')), validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, 'invalid image_base64')
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(413, 'image too large')
        if not settings.vision_enabled:
            raise HTTPException(503, 'vision is disabled')
        result = await media.perceive(raw, str(payload.get('prompt') or 'Describe observable evidence only.'), str(payload.get('mime') or 'image/jpeg'))
        await store_fact_if_present(store, result, payload)
        return result

    @app.get('/api/self/inspect')
    async def self_inspect(_: None = Depends(require_auth)):
        return {'status': 'SUCCESS', 'repository': str(maintenance.root), 'files': maintenance.inventory()}

    @app.get('/api/self/read')
    async def self_read(path: str, _: None = Depends(require_auth)):
        try:
            return {'status': 'SUCCESS', 'path': path, 'content': maintenance.read(path)}
        except Exception as exc:
            raise HTTPException(400, str(exc))

    @app.get('/api/self/verify')
    async def self_verify(_: None = Depends(require_auth)):
        return maintenance.verify()

    @app.get('/api/federation/nodes')
    async def federation_nodes(_: None = Depends(require_auth)):
        return {'nodes': nodes.reconcile()}

    @app.get('/api/integrations/{provider_name}/calendar')
    async def integration_calendar(provider_name: str, account_id: str = '', _: None = Depends(require_auth)):
        if provider_name not in oauth.PROFILES:
            raise HTTPException(400, 'unsupported OAuth provider')
        try:
            return await oauth.calendar(provider_name, account_id or None)
        except Exception as exc:
            raise HTTPException(503, str(exc))

    @app.get('/api/integrations/{provider_name}/mail')
    async def integration_mail(provider_name: str, account_id: str = '', _: None = Depends(require_auth)):
        if provider_name not in oauth.PROFILES:
            raise HTTPException(400, 'unsupported OAuth provider')
        try:
            return await oauth.mail(provider_name, account_id or None)
        except Exception as exc:
            raise HTTPException(503, str(exc))

    @app.post('/api/events/signed')
    async def signed_event(payload: dict, signature: str, _: None = Depends(require_auth)):
        import hashlib, hmac, json
        if not settings.event_hmac_secret:
            raise HTTPException(503, 'event HMAC secret is not configured')
        raw = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
        expected = hmac.new(settings.event_hmac_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(401, 'invalid event signature')
        event = Event(payload.get('type', 'signed.external'), payload, 'signed-external')
        if events is not None:
            await events.publish(event)
        return {'status': 'ACCEPTED', 'event': payload, 'published': events is not None}


def store_fact_if_present(store, result, payload):
    observation = result.get('observation') if isinstance(result, dict) else None
    if observation:
        store.fact(observation, 'vision', '', 0.65, {'prompt': payload.get('prompt', '')})
