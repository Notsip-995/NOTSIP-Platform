from __future__ import annotations
import ast,operator,os,platform,subprocess,webbrowser
from pathlib import Path
from .policy import Risk
class Tool:
    def __init__(self,name,desc,capability,risk,schema,fn,destructive=False):self.name=name;self.desc=desc;self.capability=capability;self.risk=risk;self.schema=schema;self.fn=fn;self.destructive=destructive
    def openai(self):return {'type':'function','function':{'name':self.name,'description':self.desc,'parameters':self.schema}}
class Registry:
    def __init__(self):self.items={}
    def add(self,t):self.items[t.name]=t
    def get(self,n):return self.items.get(n)
    def all(self):return list(self.items.values())
    def schemas(self):return [t.openai() for t in self.all()]
def calc(expr):
    node=ast.parse(expr,mode='eval').body;ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.Mod:operator.mod}
    def ev(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.UnaryOp) and type(n.op) in (ast.UAdd,ast.USub):return (+1 if isinstance(n.op,ast.UAdd) else -1)*ev(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in ops:return ops[type(n.op)](ev(n.left),ev(n.right))
        raise ValueError('unsupported expression')
    return ev(node)
class Workspace:
    def __init__(self,root):self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
    def path(self,rel):
        p=(self.root/rel).resolve()
        if self.root not in p.parents and p!=self.root:raise PermissionError('outside NOTSIP workspace')
        return p
    def read(self,rel):return self.path(rel).read_text(encoding='utf-8')
    def write(self,rel,content):p=self.path(rel);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8');return str(p.relative_to(self.root))
    def list(self,q=''):return [str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file() and (not q or q.lower() in p.name.lower())][:500]
class Windows:
    def __init__(self,workspace):self.workspace=workspace
    def exec(self,command,timeout=60):
        if platform.system()!='Windows':raise RuntimeError('Windows node required')
        p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',command],cwd=str(self.workspace.root),capture_output=True,text=True,timeout=max(1,min(int(timeout),180)))
        return {'status':'SUCCESS' if p.returncode==0 else 'FAILURE','returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-20000:]}
    def screenshot(self,filename='desktop.png'):
        if platform.system()!='Windows':raise RuntimeError('Windows node required')
        t=self.workspace.path(filename);e=str(t).replace("'","''");cmd=f"Add-Type -AssemblyName System.Drawing;Add-Type -AssemblyName System.Windows.Forms;$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;$i=New-Object System.Drawing.Bitmap $b.Width,$b.Height;$g=[System.Drawing.Graphics]::FromImage($i);$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);$i.Save('{e}',[System.Drawing.Imaging.ImageFormat]::Png);$g.Dispose();$i.Dispose()";r=self.exec(cmd,30)
        if r['status']!='SUCCESS':raise RuntimeError(r['stderr'] or 'screenshot failed')
        return {'status':'SUCCESS','path':str(t.relative_to(self.workspace.root)),'size':t.stat().st_size}
def open_target(target):
    try: opened=bool(webbrowser.open(target))
    except Exception as exc: return {'status':'FAILURE','opened':False,'target':target,'error':str(exc)}
    return {'status':'SUCCESS' if opened else 'UNKNOWN','opened':opened,'target':target,'note':'launch requested; target application/browser state was not independently verified'}
