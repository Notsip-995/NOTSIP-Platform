from __future__ import annotations
import platform,time

class WindowsAutomation:
    """Windows UI Automation with discovery, control-tree inspection and explicit verification states."""
    def _backend(self):
        if platform.system()!='Windows':raise RuntimeError('Windows node required')
        try:from pywinauto import Desktop
        except Exception as e:raise RuntimeError('pywinauto is required for broad Windows automation') from e
        return Desktop
    def _desktop(self):return self._backend()(backend='uia')
    def windows(self,title_re='.*'):return [w.window_text() for w in self._desktop().windows(title_re=title_re)]
    def focus(self,title='',title_re=''):
        w=self._desktop().window(title_re=title_re) if title_re else self._desktop().window(title=title);w.wait('visible',timeout=10);w.set_focus();return {'status':'SUCCESS','title':w.window_text()}
    def _root(self,window_title='',window_re=''):
        r=self._desktop().window(title_re=window_re) if window_re else self._desktop().window(title=window_title);r.wait('visible',timeout=10);return r
    def control_tree(self,window_title='',window_re='',depth=5):
        root=self._root(window_title,window_re);out=[];errors=[]
        def walk(c,d,parent=''):
            if d>depth:return
            try:
                out.append({'path':parent,'title':c.window_text(),'control_type':c.element_info.control_type,'automation_id':getattr(c.element_info,'automation_id',''),'enabled':c.is_enabled()})
                children=c.children()
            except Exception as exc:
                errors.append({'path':parent,'error':str(exc)});return
            for i,ch in enumerate(children):walk(ch,d+1,f'{parent}/{i}')
        walk(root,0,'');status='SUCCESS' if not errors else 'PARTIAL_SUCCESS'
        return {'status':status,'window':root.window_text(),'controls':out[:1000],'errors':errors[:200],'verified':not errors}
    def _control(self,window_title='',window_re='',control_type='Button',title='',title_re='',automation_id=''):
        r=self._root(window_title,window_re);kwargs={'control_type':control_type}
        if automation_id:kwargs['auto_id']=automation_id
        if title:kwargs['title']=title
        if title_re:kwargs['title_re']=title_re
        return r.child_window(**kwargs)
    def click(self,control_type='Button',title='',title_re='',window_title='',window_re='',automation_id='',verify_title=''):
        ctl=self._control(window_title,window_re,control_type,title,title_re,automation_id);before=ctl.window_text() if verify_title else None;ctl.wait('enabled',timeout=10);ctl.click_input();time.sleep(.15)
        if verify_title:
            after=ctl.window_text()
            return {'status':'SUCCESS','control':after,'verified':after==verify_title} if after==verify_title else {'status':'FAILURE','error':'post-click verification failed','before':before,'after':after,'verified':False}
        return {'status':'UNKNOWN','control':ctl.window_text(),'verified':False,'note':'click was dispatched but no post-action state was requested for verification'}
    def type_text(self,text,control_type='Edit',title='',title_re='',window_title='',window_re='',clear=True,verify=True):
        ctl=self._control(window_title,window_re,control_type,title,title_re);ctl.wait('enabled',timeout=10);ctl.set_focus()
        if clear:ctl.type_keys('^a')
        ctl.type_keys(text,with_spaces=True)
        if not verify:return {'status':'UNKNOWN','control':ctl.window_text(),'verified':False,'note':'typing was dispatched without verification'}
        try:actual=ctl.get_value() if hasattr(ctl,'get_value') else ctl.window_text()
        except Exception as exc:return {'status':'UNKNOWN','control':ctl.window_text(),'verified':False,'note':f'text entered but value could not be read back: {exc}'}
        if text and text not in str(actual):return {'status':'FAILURE','error':'text verification failed','verified':False}
        return {'status':'SUCCESS','control':ctl.window_text(),'verified':True}
    def hotkey(self,*keys):
        from pywinauto.keyboard import send_keys
        send_keys('+'.join(keys));time.sleep(.05);return {'status':'UNKNOWN','keys':list(keys),'verified':False,'note':'key sequence dispatched; resulting application state was not independently verified'}
    def press(self,key):
        if key.lower() in {'enter','esc','escape','tab','space','backspace','delete','home','end'}:return self.hotkey(key)
        raise ValueError('unsupported key; use hotkey for modified keys')
    def clipboard_get(self):
        import pyperclip
        return {'status':'SUCCESS','text':pyperclip.paste(),'verified':True}
    def clipboard_set(self,text):
        import pyperclip
        pyperclip.copy(text)
        actual=pyperclip.paste()
        return {'status':'SUCCESS' if actual==text else 'FAILURE','bytes':len(text.encode()),'verified':actual==text}
    def mouse_click(self,x:int,y:int,button='left'):
        from pywinauto import mouse
        if button not in {'left','right','middle'}:raise ValueError('unsupported mouse button')
        mouse.click(button=button,coords=(x,y));return {'status':'UNKNOWN','x':x,'y':y,'button':button,'verified':False,'note':'mouse event dispatched; resulting state was not independently verified'}
    def wait_for_window(self,title_re='.*',timeout=15):
        end=time.time()+timeout
        while time.time()<end:
            try:
                w=self._desktop().window(title_re=title_re)
                if w.exists(timeout=.2):return {'status':'SUCCESS','title':w.window_text(),'verified':True}
            except Exception:
                time.sleep(.25)
                continue
            time.sleep(.25)
        return {'status':'FAILURE','error':'window timeout','title_re':title_re,'verified':False}
