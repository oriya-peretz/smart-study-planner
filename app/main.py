from fastapi import FastAPI

app = FastAPI(title="Smart Study Planner")


@app.get("/health")
def health():
    return {"status": "ok"}
