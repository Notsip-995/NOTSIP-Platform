import email,imaplib,ipaddress,json,smtplib,socket,ssl,urllib.parse,uuid,os,shutil,platform
from email.message import EmailMessage
from pathlib import Path
import httpx
from .config import settings
class Web:
    def __init__(self,key=''):self.key=key or ''
    @property
    def _key(self):return settings.brave_api_key
    @property
    def enabled(self):return bool(self._key)
    async def search(self,q,count=5):
        if not self.enabled:raise RuntimeError('web search not configured')
        async with httpx.AsyncClient(timeout=20) as c:r=await c.get('https://api.search.brave.com/res/v1/web/search',params={'q':q,'count':count},headers={'Accept':'application/json','X-Subscription-Token':self._key});r.raise_for_status();d=r.json()
        return [{'title':x.get('title'),'url':x.get('url'),'description':x.get('description')} for x in d.get('web',{}).get('results',[])]
class Email:
    def __init__(self,smtp_host='',smtp_port=587,imap_host='',username='',password=''):self.smtp_host=smtp_host;self.smtp_port=int(smtp_port);self.imap_host=imap_host;self.username=username;self.password=password
    @property
    def _username(self):return settings.email_username
    @property
    def _password(self):return settings.email_password
    @property
    def _smtp_host(self):return settings.smtp_host
    @property
    def _smtp_port(self):return int(settings.smtp_port or 587)
    @property
    def _imap_host(self):return settings.imap_host
    @property
    def enabled(self):return bool(self._username and self._password and (self._smtp_host or self._imap_host))
    def send(self,to,subject,body):
        if not self.enabled or not self._smtp_host:raise RuntimeError('SMTP not configured')
        m=EmailMessage();m['From']=self._username;m['To']=to;m['Subject']=subject;m.set_content(body)
        if self._smtp_port==465:
            with smtplib.SMTP_SSL(self._smtp_host,self._smtp_port,timeout=20,context=ssl.create_default_context()) as s:s.login(self._username,self._password);s.send_message(m)
        else:
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
        data={'grant_type':'authorization_code','code':code,'client_id':self.client_id,'redirect_uri':self.redirect}
        if self.client_secret:data['client_secret']=self.client_secret
        async with httpx.AsyncClient(timeout=20) as c:r=await c.post(self.token,data=data);r.raise_for_status();return r.json()
def _public_host(host):
    try:
        if host.lower() in {'localhost','localhost.localdomain'}:return False
        addrs=socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)
        return bool(addrs) and all(not (ipaddress.ip_address(a[4][0]).is_private or ipaddress.ip_address(a[4][0]).is_loopback or ipaddress.ip_address(a[4][0]).is_link_local or ipaddress.ip_address(a[4][0]).is_multicast or ipaddress.ip_address(a[4][0]).is_reserved) for a in addrs)
    except Exception:return False

def _browser_executable():
    override=os.getenv('NOTSIP_BROWSER_EXECUTABLE','').strip()
    if override and Path(override).is_file():return override
    for name in ('chrome','google-chrome','chromium','chromium-browser','msedge'):
        found=shutil.which(name)
        if found:return found
    if platform.system()=='Windows':
        candidates=[
            Path(os.getenv('PROGRAMFILES','C:\\Program Files'))/'Google/Chrome/Application/chrome.exe',
            Path(os.getenv('PROGRAMFILES(X86)','C:\\Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
            Path(os.getenv('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe',
            Path(os.getenv('PROGRAMFILES','C:\\Program Files'))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.getenv('PROGRAMFILES(X86)','C:\\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
        ]
        for p in candidates:
            if p.is_file():return str(p)
    return ''
class Browser:
    async def extract(self,url,wait_ms=1000):
        if not settings.browser_enabled:raise RuntimeError('browser automation is disabled')
        parsed=urllib.parse.urlparse(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:raise ValueError('browser extraction requires a public http(s) URL')
        if not _public_host(parsed.hostname):raise ValueError('browser extraction blocks private, loopback, link-local, multicast, and reserved addresses')
        try:from playwright.async_api import async_playwright
        except Exception as e:raise RuntimeError('Playwright is unavailable in this installation') from e
        async with async_playwright() as p:
            launch={}
            executable=_browser_executable()
            if executable:launch['executable_path']=executable
            try:b=await p.chromium.launch(headless=True,**launch)
            except Exception as exc:
                raise RuntimeError('No usable Chromium-compatible browser is installed; install Google Chrome/Edge or set NOTSIP_BROWSER_EXECUTABLE') from exc
            page=await b.new_page()
            async def guard(route):
                target=urllib.parse.urlparse(route.request.url)
                if target.scheme not in {'http','https'} or not target.hostname or not _public_host(target.hostname):await route.abort();return
                await route.continue_()
            await page.route('**/*',guard)
            await page.goto(url,wait_until='domcontentloaded',timeout=30000);await page.wait_for_timeout(wait_ms);r={'url':page.url,'title':await page.title(),'text':(await page.locator('body').inner_text())[:50000]};await b.close();return r
