from __future__ import annotations
import os,platform
from urllib.parse import urlparse
from fastapi import Depends


def _configured(value):return bool(str(value or '').strip())

def _database_configured(value):return _configured(value) and (str(value).startswith('sqlite:///') or str(value).startswith('postgresql://') or str(value).startswith('postgres://'))

def attach(app,require_auth,settings,store):
    app.router.routes=[r for r in app.router.routes if getattr(r,'path',None)!='/api/setup/readiness']
    @app.get('/api/setup/readiness')
    async def setup_readiness(_:None=Depends(require_auth)):
        devices=store.devices('primary-user')
        checks=[
            {'id':'llm','label':'Reasoning provider','configured':(_configured(settings.llm_base_url) and _configured(settings.llm_model) and _configured(settings.llm_api_key)) or (_configured(settings.fallback_llm_base_url) and _configured(settings.fallback_llm_model) and _configured(settings.fallback_llm_api_key)),'kind':'user_configuration','required':True,'detail':'Configure a primary or fallback reasoning provider.'},
            {'id':'authentication','label':'Remote authentication','configured':_configured(settings.api_key) or (_configured(settings.oidc_issuer) and _configured(settings.oidc_client_id) and _configured(settings.oidc_redirect_uri)),'kind':'user_configuration','required':False,'detail':'Configure an API key for self-hosted remote access or complete OIDC when federated authentication is desired; local loopback remains available.'},
            {'id':'database','label':'Database backend','configured':_database_configured(settings.database_url),'kind':'user_configuration','required':True,'detail':'Configure SQLite or PostgreSQL before startup; changing the backend at runtime is intentionally disabled.'},
            {'id':'stt','label':'Speech-to-text','configured':_configured(settings.stt_base_url) and _configured(settings.stt_model) and _configured(settings.stt_api_key),'kind':'user_configuration','required':False,'detail':'Configure STT for voice transcription.'},
            {'id':'tts','label':'Text-to-speech','configured':_configured(settings.tts_base_url) and _configured(settings.tts_model) and _configured(settings.tts_api_key),'kind':'user_configuration','required':False,'detail':'Configure TTS for spoken responses.'},
            {'id':'speaker_identity','label':'Speaker identity verification','configured':_configured(settings.speaker_identity_url) and _configured(settings.speaker_identity_token),'kind':'user_configuration','required':False,'detail':'Configure a real speaker-verification provider before unverified microphone input can establish a trusted actor for high-risk actions.'},
            {'id':'web_search','label':'Web search','configured':_configured(settings.brave_api_key),'kind':'user_configuration','required':False,'detail':'Configure Brave Search for current web retrieval.'},
            {'id':'email','label':'Email','configured':_configured(settings.email_username) and _configured(settings.email_password) and (_configured(settings.smtp_host) or _configured(settings.imap_host)),'kind':'user_configuration','required':False,'detail':'Configure SMTP/IMAP for mail operations; authenticated SMTP requires TLS.'},
            {'id':'oidc','label':'External identity provider','configured':_configured(settings.oidc_issuer) and _configured(settings.oidc_client_id) and _configured(settings.oidc_redirect_uri),'kind':'user_configuration','required':False,'detail':'Configure OIDC only when federated authentication is desired.'},
            {'id':'android','label':'Android device','configured':bool(devices),'kind':'user_setup','required':False,'detail':'Install, pair, and grant Android background/accessibility permissions for mobile control.'},
            {'id':'windows_signing','label':'Windows release signing','configured':_configured(getattr(settings,'windows_publisher_thumbprint','')),'kind':'release_configuration','required':False,'detail':'Configure the trusted publisher thumbprint and signing material before signed updates/releases.'},
            {'id':'remote_compute','label':'Remote compute','configured':_configured(settings.remote_compute_url) and _configured(settings.remote_compute_token),'kind':'user_configuration','required':False,'detail':'Configure an authorized HTTPS remote compute provider.'},
            {'id':'remote_sensing','label':'Remote sensing','configured':_configured(settings.remote_sensing_url) and _configured(settings.remote_sensing_token),'kind':'user_configuration','required':False,'detail':'Configure an authorized HTTPS remote-sensing provider.'},
            {'id':'home','label':'Home/building control','configured':_configured(settings.home_adapter_url) and _configured(settings.home_adapter_token),'kind':'user_configuration','required':False,'detail':'Configure an authorized HTTPS home/building adapter.'},
            {'id':'biometric','label':'Biometric telemetry','configured':_configured(settings.biometric_adapter_url) and _configured(settings.biometric_adapter_token),'kind':'user_configuration','required':False,'detail':'Configure an authorized HTTPS telemetry provider; NOTSIP does not diagnose.'},
            {'id':'aviation','label':'Flight planning','configured':_configured(settings.flight_planning_url) and _configured(settings.flight_planning_token),'kind':'user_configuration','required':False,'detail':'Configure an authorized HTTPS flight-planning provider; NOTSIP does not control aircraft.'},
            {'id':'business','label':'Business administration','configured':_configured(settings.business_admin_url) and _configured(settings.business_admin_token),'kind':'user_configuration','required':False,'detail':'Configure an authorized HTTPS enterprise administration provider.'},
            {'id':'federation','label':'Federation secret','configured':_configured(settings.node_shared_secret),'kind':'user_configuration','required':False,'detail':'Configure the shared federation secret before joining trusted nodes.'},
            {'id':'voice_hardware','label':'Native voice hardware','configured':platform.system()=='Windows' and bool(getattr(settings,'native_voice_enabled',False)),'kind':'external_environment','required':False,'detail':'Requires Windows and working microphone/audio hardware plus configured STT/TTS services.'},
        ]
        required=[x for x in checks if x['required'] and not x['configured']]
        external=[x for x in checks if x['kind']=='external_environment' and not x['configured']]
        return {'status':'READY_FOR_USER_CONFIGURATION' if not required else 'REQUIRED_CONFIGURATION_MISSING','required_blockers':required,'checks':checks,'external_environment_gates':external,'core_runtime':{'platform':platform.system(),'python':platform.python_version(),'data_dir':os.path.abspath(str(settings.data_dir))},'paired_devices':len(devices)}
