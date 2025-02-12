from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.post("/api/v1/scene-detection/process")
async def scene_detection():
    return {
        "status": "success",
        "message": "处理成功",
        "task_id": "123",
        "output_dir": "/path/to/output",
        "data": [
            {
                "start_frame": 0,
                "end_frame": 120,
                "start_time": "00:00:00",
                "end_time": "00:00:05"
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)