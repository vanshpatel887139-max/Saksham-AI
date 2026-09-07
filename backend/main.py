"""SakshamAI FastAPI backend entrypoint.

Run:
    uvicorn main:app --reload --port 8000

This starts an API on http://localhost:8000 with CORS enabled for the
Vite frontend running on http://localhost:3000.
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth, users, competency, courses, quiz, admin, assistant, labs, igot


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite schema + seed demo data on startup
    init_db()
    yield


app = FastAPI(
    title="SakshamAI API",
    version="0.1.0",
    description="Skill Intelligence Platform for Official Statistics — SIH demo backend",
    lifespan=lifespan,
)

# CORS: allow the Vite dev server and preview to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.11.23:3000",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(competency.router)
app.include_router(courses.router)
app.include_router(quiz.router)
app.include_router(admin.router)
app.include_router(assistant.router)
app.include_router(labs.router)
app.include_router(igot.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "sakshamai-backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)