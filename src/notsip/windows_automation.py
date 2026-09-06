from __future__ import annotations
import platform, time

class WindowsAutomation:
    """Windows UI Automation with discovery, control-tree inspection and verification."""
    def _backend(self):
        if platform.system()!='Windows':raise RuntimeError('Windows node required')
        try:
            from pywinauto import Desktop
        except Exception as e:raise RuntimeError('pywinauto is required for broad Windows automation') from e
        return Desktop
    def _desktop(self):return self._backend()(backend='uia')
    def windows(self,title_re='.*'):return [w.window_text() for w in self._desktop().windows(title_re=title_re)]
    def focus(self,title='',title_re=''):
        w=self._desktop().window(title_re=title_re) if title_re else self._desktop().window(title=title);w.wait('visible',timeout=10);w.set_focus();return {'status':'SUCCESS','title':w.window_text()}
    def _root(self,window_title='',window_re=''):
        r=self._desktop().window(title_re=window_re) if window_re else self._desktop().window(title=window_title);r.wait('visible',timeout=10);return r
    def control_tree(self,window_title='',window_re='',depth=5):
        root=self._root(window_title,window_re);out=[]
        def walk(c,d,parent=''):
            if d>depth:return
            try:
                out.append({'path':parent,'title':c.window_text(),'control_type':c.element_info.control_type,'automation_id':getattr(c.element_info,'automation_id',''),'enabled':c.is_enabled()})
                for i,ch in enumerate(c.children()):walk(ch,d+1,f'{parent}/{i}')
            except Exception:pass
        walk(root,0,'');return {'status':'SUCCESS','window':root.window_text(),'controls':out[:1000]}
    def _control(self,window_title='',window_re='',control_type='Button',title='',title_re='',automation_id=''):
        r=self._root(window_title,window_re);kwargs={'control_type':control_type}
        if automation_id:kwargs['auto_id']=automation_id
        if title:kwargs['title']=title
        if title_re:kwargs['title_re']=title_re
        return r.child_window(**kwargs)
    def click(self,control_type='Button',title='',title_re='',window_title='',window_re='',automation_id='',verify_title=''):
        ctl=self._control(window_title,window_re,control_type,title,title_re,automation_id);before=ctl.window_text() if verify_title else ''
        ctl.wait('enabled',timeout=10);ctl.click_input();time.sleep(.15)
        if verify_title and ctl.window_text()!=verify_title:return {'status':'FAILURE','error':'post-click verification failed','before':before,'after':ctl.window_text()}
        return {'status':'SUCCESS','control':ctl.window_text()}
    def type_text(self,text,control_type='Edit',title='',title_re='',window_title='',window_re='',clear=True,verify=True):
        ctl=self._control(window_title,window_re,control_type,title,title_re);ctl.wait('enabled',timeout=10);ctl.set_focus()
        if clear:ctl.type_keys('^a')
        ctl.type_keys(text,with_spaces=True)
        if verify:
            try:
                actual=ctl.get_value() if hasattr(ctl,'get_value') else ctl.window_text()
                if text and text not in str(actual):return {'status':'FAILURE','error':'text verification failed'}
            except Exception:pass
        return {'status':'SUCCESS','control':ctl.window_text()}
    def hotkey(self,*keys):
        from pywinauto.keyboard import send_keys
        send_keys('+'.join(keys));time.sleep(.05);return {'status':'SUCCESS','keys':list(keys)}
    def press(self,key):
        if key.lower() in {'enter','esc','escape','tab','space','backspace','delete','home','end'}:return self.hotkey(key)
        raise ValueError('unsupported key; use hotkey for modified keys')
    def clipboard_get(self):
        import pyperclip
        return {'status':'SUCCESS','text':pyperclip.paste()}
    def clipboard_set(self,text):
        import pyperclip
        pyperclip.copy(text);return {'status':'SUCCESS','bytes':len(text.encode())}
    def mouse_click(self,x:int,y:int,button='left'):
        from pywinauto import mouse
        mouse.click(button=button,coords=(x,y));return {'status':'SUCCESS','x':x,'y':y,'button':button}
    def wait_for_window(self,title_re='.*',timeout=15):
        end=time.time()+timeout
        while time.time()<end:
            try:
                w=self._desktop().window(title_re=title_re)
                if w.exists(timeout=.2):return {'status':'SUCCESS','title':w.window_text()}
            except Exception:pass
            time.sleep(.25)
        return {'status':'FAILURE','error':'window timeout','title_re':title_re}
