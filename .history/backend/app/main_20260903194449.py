from fastapi import FastAPI

app = FastAPI(
    title="Revenue Recovery API",
    description="AI-powered revenue recovery platform",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "Revenue Recovery API is running 🚀"
    }