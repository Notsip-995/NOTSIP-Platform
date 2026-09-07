        checks['web_search']={'ok':bool(self.web and self.web.enabled),'detail':'configured' if self.web and self.web.enabled else 'not configured'}
        checks['email']={'ok':bool(self.email and self.email.enabled),'detail':'configured' if self.email and self.email.enabled else 'not configured'}
        checks['oauth']={'ok':bool(self.auth and self.auth.oidc.configured),'detail':'configured' if self.auth and self.auth.oidc.configured else 'not configured'}
        checks['browser']={'ok':bool(getattr(s,'browser_enabled',True)),'detail':'enabled' if getattr(s,'browser_enabled',True) else 'disabled'}
        checks['windows_uia']={'ok':platform.system()=='Windows','detail':'ready' if platform.system()=='Windows' else 'Windows node required'}
        checks['android']={'ok':bool(self.store and self.store.devices()),'detail':'paired device present' if self.store and self.store.devices() else 'no paired Android device'}
        checks['scheduler']={'ok':True,'detail':'durable scheduler available'}
        checks['federation']={'ok':bool(self.nodes),'detail':'node registry available' if self.nodes else 'not initialized'}
        checks['recovery']={'ok':True,'detail':'checkpoint available' if self.recovery and self.recovery.verify_latest()['valid'] else 'checkpoint not yet created'}
        checks['security']={'ok':bool(self.auth),'detail':'security manager initialized' if self.auth else 'security manager unavailable'}
        core_names={'python','platform','storage','database','llm','scheduler','federation','security'}
        optional_names=set(checks)-core_names
        core_ok=all(checks[k]['ok'] for k in core_names if k in checks)
        optional_missing=[k for k in optional_names if not checks[k]['ok']]
        return {'ok':core_ok,'core_ok':core_ok,'optional_missing':optional_missing,'checks':checks,'timestamp':time.time()}
