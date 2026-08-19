"""Launch the FastAPI backend: uvicorn productpilot.api:app"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("productpilot.api:app", host="0.0.0.0", port=8000, reload=False)