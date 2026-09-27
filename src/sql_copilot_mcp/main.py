from fastapi import FastAPI

app = FastAPI(title="SQL Copilot")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}