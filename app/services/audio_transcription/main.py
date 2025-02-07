from fastapi import FastAPI
from .routes import router

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    print("\nAPI Documentation available at: http://127.0.0.1:6001/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=6001)