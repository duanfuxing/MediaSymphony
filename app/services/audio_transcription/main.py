from fastapi import FastAPI
from routes import router
from config import settings

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    print(f"\nAPI Documentation available at: http://{settings.HOST}:{settings.PORT}/docs\n")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)