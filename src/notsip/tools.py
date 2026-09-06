from __future__ import annotations
import ast,operator,os,platform,subprocess
from pathlib import Path
from .policy import Risk
class Tool:
    def __init__(self,name,description,capability,risk,schema,fn,destructive=False): self.name=name; self.description=description; self.capability=capability; self.risk=risk; self.schema=schema; self.fn=fn; self.destructive=destructive
    def schema_openai(self): return {'type':'function','function':{'name':self.name,'description':self.description,'parameters':self.schema}}
class Registry:
    def __init__(self): self.tools={}
    def add(self,t): self.tools[t.name]=t
    def get(self,n): return self.tools.get(n)
    def all(self): return list(self.tools.values())
    def schemas(self): return [t.schema_openai() for t in self.all()]
def calc(expr):
    node=ast.parse(expr,mode='eval').body; ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.Mod:operator.mod}
    def ev(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)): return +ev(n.operand) if isinstance(n.op,ast.UAdd) else -ev(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in ops: return ops[type(n.op)](ev(n.left),ev(n.right))
        raise ValueError('unsupported expression')
    return ev(node)
def list_workspace(workspace,query=''):
    root=Path(workspace).resolve(); out=[]
    for p in root.rglob('*'):
        if p.is_file() and (not query or query.lower() in p.name.lower()): out.append(str(p.relative_to(root)))
        if len(out)>=200: break
    return {'status':'SUCCESS','files':out}
def read_workspace(workspace,path):
    root=Path(workspace).resolve(); target=(root/path).resolve()
    if root not in target.parents and target!=root: raise PermissionError('path outside NOTSIP workspace')
    return {'status':'SUCCESS','path':str(target.relative_to(root)),'content':target.read_text(encoding='utf-8')}
def windows_exec(workspace,command,timeout=30):
    if platform.system()!='Windows': raise RuntimeError('windows_exec is only available on Windows nodes')
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],cwd=workspace,capture_output=True,text=True,timeout=max(1,min(timeout,120)))
    return {'status':'SUCCESS' if p.returncode==0 else 'FAILURE','returncode':p.returncode,'stdout':p.stdout[-12000:],'stderr':p.stderr[-12000:]}
def diagnostics(workspace):
    root=Path(workspace).resolve(); return {'status':'SUCCESS','platform':platform.platform(),'python':platform.python_version(),'workspace':str(root),'workspace_exists':root.exists()}
