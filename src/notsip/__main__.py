import uvicorn
from .config import settings
from .core_runtime import app

def main():uvicorn.run(app,host=settings.host,port=settings.port)
if __name__=='__main__':main()
