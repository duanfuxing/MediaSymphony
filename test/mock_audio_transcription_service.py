from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.post("/api/v1/audio-transcription/process")
async def audio_transcription():
    return {
        "status": "success",
        "task_id": "789",
        "transcription": "转写的文本内容",
        "transcription_path": "/path/to/processed/transcription.txt",
        "segments": [
            {
                "start": 0.0,
                "end": 2.5,
                "text": "分段文本内容"
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)