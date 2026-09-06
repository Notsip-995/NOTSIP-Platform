from __future__ import annotations
import platform, time

class WindowsAutomation:
    """UI Automation adapter. pywinauto is optional until a Windows node calls it."""
    def _backend(self):
        if platform.system()!='Windows': raise RuntimeError('Windows node required')
        try:
            from pywinauto import Desktop
        except Exception as e: raise RuntimeError('pywinauto is required for broad Windows automation') from e
        return Desktop
    def windows(self, title_re='.*'):
        Desktop=self._backend(); return [w.window_text() for w in Desktop(backend='uia').windows(title_re=title_re)]
    def focus(self,title='',title_re=''):
        Desktop=self._backend(); kwargs={'backend':'uia'}; w=Desktop(**kwargs).window(title_re=title_re) if title_re else Desktop(**kwargs).window(title=title); w.wait('visible',timeout=10); w.set_focus(); return {'status':'SUCCESS','title':w.window_text()}
    def click(self,control_type='Button',title='',title_re='',window_title='',window_re=''):
        Desktop=self._backend(); root=Desktop(backend='uia').window(title_re=window_re) if window_re else Desktop(backend='uia').window(title=window_title)
        root.wait('visible',timeout=10)
        ctl=root.child_window(title_re=title_re, title=title, control_type=control_type); ctl.wait('enabled',timeout=10); ctl.click_input(); return {'status':'SUCCESS','control':ctl.window_text()}
    def type_text(self,text,control_type='Edit',title='',title_re='',window_title='',window_re='',clear=True):
        Desktop=self._backend(); root=Desktop(backend='uia').window(title_re=window_re) if window_re else Desktop(backend='uia').window(title=window_title)
        ctl=root.child_window(title_re=title_re,title=title,control_type=control_type); ctl.wait('enabled',timeout=10); ctl.set_focus();
        if clear: ctl.type_keys('^a')
        ctl.type_keys(text,with_spaces=True); return {'status':'SUCCESS','control':ctl.window_text()}
    def hotkey(self,*keys):
        Desktop=self._backend(); from pywinauto.keyboard import send_keys; send_keys('+'.join(keys)); time.sleep(.05); return {'status':'SUCCESS','keys':list(keys)}
    def press(self,key):
        if key.lower() in {'enter','esc','escape','tab','space','backspace','delete','home','end'}: return self.hotkey(key)
        raise ValueError('unsupported key; use hotkey for modified keys')
