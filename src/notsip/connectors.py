from __future__ import annotations
import email,imaplib,json,smtplib,ssl,urllib.parse,uuid
from email.message import EmailMessage
from pathlib import Path
import httpx
from .config import settings
class Web:
    def __init__(self,key=''):self.key=key or ''
    @property
    def _key(self):return settings.brave_api_key or self.key
    @property
    def enabled(self):return bool(self._key)
    async def search(self,q,count=5):
        if not self.enabled:raise RuntimeError('web search not configured')
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get('https://api.search.brave.com/res/v1/web/search',params={'q':q,'count':count},headers={'Accept':'application/json','X-Subscription-Token':self._key});r.raise_for_status();d=r.json()
        return [{'title':x.get('title'),'url':x.get('url'),'description':x.get('description')} for x in d.get('web',{}).get('results',[])]
class Email:
    def __init__(self,smtp_host='',smtp_port=587,imap_host='',username='',password=''):self.smtp_host=smtp_host;self.smtp_port=int(smtp_port);self.imap_host=imap_host;self.username=username;self.password=password
    @property
    def _username(self):return settings.email_username or self.username
    @property
    def _password(self):return settings.email_password or self.password
    @property
    def _smtp_host(self):return settings.smtp_host or self.smtp_host
    @property
    def _smtp_port(self):return int(settings.smtp_port or self.smtp_port)
    @property
    def _imap_host(self):return settings.imap_host or self.imap_host
    @property
    def enabled(self):return bool(self._username and self._password and (self._smtp_host or self._imap_host))
    def send(self,to,subject,body):
        if not self.enabled or not self._smtp_host:raise RuntimeError('SMTP not configured')
        m=EmailMessage();m['From']=self._username;m['To']=to;m['Subject']=subject;m.set_content(body)
        with smtplib.SMTP(self._smtp_host,self._smtp_port,timeout=20) as s:
            if self._smtp_port!=25:s.starttls(context=ssl.create_default_context())
            s.login(self._username,self._password);s.send_message(m)
        return {'status':'SUCCESS','to':to,'subject':subject}
    def search(self,mailbox='INBOX',criteria='ALL',limit=20):
        if not self.enabled or not self._imap_host:raise RuntimeError('IMAP not configured')
        c=imaplib.IMAP4_SSL(self._imap_host);c.login(self._username,self._password);c.select(mailbox,readonly=True);_,d=c.search(None,criteria);ids=d[0].split()[-limit:];out=[]
        for mid in reversed(ids):
            _,md=c.fetch(mid,'(RFC822)');msg=email.message_from_bytes(md[0][1]);out.append({'id':mid.decode(),'subject':msg.get('subject'),'from':msg.get('from'),'date':msg.get('date')})
        c.logout();return {'status':'SUCCESS','messages':out}
class Calendar:
    def parse(self,path):
        lines=Path(path).read_text(encoding='utf-8').splitlines();evs=[];b=[]
        for line in lines:
            if line=='BEGIN:VEVENT':b=[]
            elif line=='END:VEVENT':
                d={}
                for z in b:
                    if ':' in z:k,v=z.split(':',1);d[k.split(';',1)[0]]=v
                evs.append(d)
            else:b.append(line)
        return evs
    def create_ics(self,events,path):
        lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//NOTSIP//EN']
        for e in events:lines += ['BEGIN:VEVENT',f'UID:{e.get("UID",uuid.uuid4())}',f'DTSTART:{e["DTSTART"]}',f'DTEND:{e["DTEND"]}',f'SUMMARY:{e.get("SUMMARY","")}','END:VEVENT']
        lines+=['END:VCALENDAR'];p=Path(path);p.write_text('\n'.join(lines)+'\n',encoding='utf-8');return str(p)
class OAuth:
    def __init__(self,authorize='',token='',client_id='',client_secret='',redirect='',scopes=''):self.authorize=authorize;self.token=token;self.client_id=client_id;self.client_secret=client_secret;self.redirect=redirect;self.scopes=scopes
    @property
    def configured(self):return bool(self.authorize and self.token and self.client_id and self.redirect)
    def authorization_url(self,state):
        if not self.configured:raise RuntimeError('OAuth not configured')
        return self.authorize+'?'+urllib.parse.urlencode({'client_id':self.client_id,'redirect_uri':self.redirect,'response_type':'code','scope':self.scopes,'state':state})
    async def exchange(self,code):
        if not self.configured:raise RuntimeError('OAuth not configured')
        data={'grant_type':'authorization_code','code':code,'client_id':self.client_id,'redirect_uri':self.redirect};
        if self.client_secret:data['client_secret']=self.client_secret
        async with httpx.AsyncClient(timeout=20) as c:r=await c.post(self.token,data=data);r.raise_for_status();return r.json()
class Browser:
    async def extract(self,url,wait_ms=1000):
        try:from playwright.async_api import async_playwright
        except Exception as e:raise RuntimeError('Install Playwright and browser binaries') from e
        async with async_playwright() as p:
            b=await p.chromium.launch(headless=True);page=await b.new_page();await page.goto(url,wait_until='domcontentloaded',timeout=30000);await page.wait_for_timeout(wait_ms);r={'url':url,'title':await page.title(),'text':(await page.locator('body').inner_text())[:50000]};await b.close();return r
