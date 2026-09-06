from __future__ import annotations
import json, logging, os, sys, time
from logging.handlers import RotatingFileHandler
from pathlib import Path

class JsonFormatter(logging.Formatter):
    def format(self,record):
        return json.dumps({'ts':time.time(),'level':record.levelname,'logger':record.name,'message':record.getMessage(),'pid':os.getpid()},separators=(',',':'),ensure_ascii=False)

def configure(root:Path,level='INFO',max_bytes=10_485_760,backup_count=5):
    log_dir=Path(root)/'runtime';log_dir.mkdir(parents=True,exist_ok=True);path=log_dir/'notsip.log'
    logger=logging.getLogger('notsip');logger.setLevel(getattr(logging,str(level).upper(),logging.INFO));logger.handlers.clear()
    h=RotatingFileHandler(path,maxBytes=int(max_bytes),backupCount=int(backup_count),encoding='utf-8');h.setFormatter(JsonFormatter());logger.addHandler(h)
    console=logging.StreamHandler(sys.stdout);console.setFormatter(JsonFormatter());logger.addHandler(console);return logger
