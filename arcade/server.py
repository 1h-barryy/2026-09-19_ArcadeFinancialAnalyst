"""Local HTTP boundary. No credentials or hidden outcome in research responses."""
import asyncio
from pathlib import Path
import secrets
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analyst import Analyst, AnalystError
from .data import DataError, load, synthetic
from .game import Game, GameError

ROOT = Path(__file__).resolve().parent.parent


class RoundRequest(BaseModel):
    round_id: str = Field(min_length=1, max_length=64)


class Prediction(RoundRequest):
    choice: Literal["DOWN", "FLAT", "UP"]


class Question(RoundRequest):
    question: str = Field(min_length=1, max_length=600)


def create_app(mode="auto", symbol="IBM", stock_key="", openai_key="", model="gpt-4.1-mini",
               cache_dir=None, analyst=None, loader=None, clock=time.monotonic):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    advisor = analyst or Analyst(openai_key, model, ROOT / ".local" / "usage.jsonl")
    sessions = {}
    load_lock = asyncio.Lock()
    loaded = None
    last_attempt = None
    last_error = None
    stock_loader = loader or (lambda: load(mode, symbol, stock_key, cache_dir or ROOT / ".local" / "cache"))

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method == "POST":
            if request.headers.get("X-Arcade") != "1":
                return JSONResponse({"detail": "Local application request required."}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin request rejected."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(GameError)
    async def game_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(DataError)
    async def data_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(AnalystError)
    async def analyst_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    def get_game(request):
        session = sessions.get(request.cookies.get("arcade_session"))
        if not session:
            raise HTTPException(404, "No active game. Start a new shift.")
        session[1] = clock()
        return session[0]

    def state(game):
        return {**game.public(), "analyst_available": bool(advisor.key),
                "analyst_verified": advisor.verified}

    @app.get("/api/status")
    async def status():
        return {"mode": mode, "analyst_available": bool(advisor.key), "analyst_verified": advisor.verified}

    @app.post("/api/game")
    async def new_game(request: Request, response: Response):
        nonlocal loaded, last_attempt, last_error
        async with load_lock:
            if loaded is None:
                if last_attempt is not None and clock() - last_attempt < 60:
                    raise DataError(last_error or "Stock loading is cooling down; try again in a minute.")
                last_attempt = clock()
                try:
                    loaded = await asyncio.to_thread(stock_loader)
                except DataError as exc:
                    last_error = str(exc)
                    raise
            elif all(data.source == "SYNTHETIC DEMO" for data in loaded[0]):
                # Retain the mode/fallback notice, but never replay cached fictional paths.
                # Previously created games still own their original immutable datasets.
                loaded = (synthetic(), loaded[1])
        game = Game.create(*loaded, clock=clock)
        old = request.cookies.get("arcade_session")
        if old in sessions:
            del sessions[old]
        for key, (_, accessed) in list(sessions.items()):
            if clock() - accessed > 7200:
                del sessions[key]
        if len(sessions) >= 32:
            raise HTTPException(429, "Too many local games; restart the server to clear sessions.")
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = [game, clock()]
        response.set_cookie("arcade_session", session_id, httponly=True, samesite="strict", max_age=7200)
        return state(game)

    @app.get("/api/game")
    async def current_game(request: Request):
        return state(get_game(request))

    @app.post("/api/ready")
    async def ready(body: RoundRequest, request: Request):
        game = get_game(request)
        game.start(body.round_id)
        return state(game)

    @app.post("/api/predict")
    async def predict(body: Prediction, request: Request):
        game = get_game(request)
        game.predict(body.round_id, body.choice)
        return state(game)

    @app.post("/api/next")
    async def next_round(body: RoundRequest, request: Request):
        game = get_game(request)
        game.advance(body.round_id)
        return state(game)

    @app.post("/api/ask")
    async def ask(body: Question, request: Request):
        game = get_game(request)
        game.check_id(body.round_id)
        game.expire()
        round_ = game.round
        if round_.deadline is None or round_.result is not None:
            raise GameError("Research is closed. Analyst requests are only available during the countdown.")
        if round_.asking:
            raise GameError("One analyst request is already in progress.")
        if not body.question.strip():
            raise AnalystError("Enter a question between 1 and 600 characters.")
        # Count valid submissions before awaiting, including eventual provider failures.
        # Independent of the bounded conversation history and late-arriving replies.
        game.analyst_questions += 1
        round_.asking = True
        try:
            reply = await advisor.ask(body.question, round_.research, round_.history)
            round_.history.append({"question": body.question.strip(), "reply": reply})
            round_.history[:] = round_.history[-6:]
            game.expire()
            return {"reply": reply, "round_id": round_.id}
        finally:
            round_.asking = False

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
