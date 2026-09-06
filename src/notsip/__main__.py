import uvicorn
from .config import settings
from .runtime05 import app

def main():
    uvicorn.run(app, host=settings.host, port=settings.port)

if __name__ == '__main__':
    main()
