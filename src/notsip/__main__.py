import uvicorn
from notsip.config import settings
from notsip.core_runtime import app

def main():
    uvicorn.run(app, host=settings.host, port=settings.port)

if __name__ == '__main__':
    main()
