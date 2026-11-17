"""FastAPI app: public API under /api plus the built single-page app."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from raaga.audio.decode import AudioDecodeError, decode_audio
from raaga.audio.youtube import YouTubeBlocked, YouTubeInvalid, fetch_youtube_segment
from raaga.config import MAX_UPLOAD_BYTES, MIN_CLIP_S, SAMPLE_RATE
from raaga.engine import EngineContext, analyze
from raaga.notes import note_to_hz_near
from raaga.api.ratelimit import RateLimiter
from raaga.store.local import LocalExampleStore

DEFAULT_TABLE = Path(__file__).resolve().parents[3] / "data" / "ragas.json"
CHUNK = 1 << 20


@dataclass
class Settings:
    store_dir: Path
    raga_table: Path = DEFAULT_TABLE
    params_path: Path | None = None
    static_dir: Path | None = None
    analyze_per_min: int = 10
    max_upload_bytes: int = MAX_UPLOAD_BYTES


def _err(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def create_app(settings: Settings) -> FastAPI:
    store = LocalExampleStore(settings.store_dir)
    ctx = EngineContext.load(store, settings.raga_table, settings.params_path)
    limiter = RateLimiter(settings.analyze_per_min)
    app = FastAPI(title="RaaGamaalika", docs_url=None, redoc_url=None)
    app.state.ctx = ctx

    async def _analyze_path(path: Path, shruti: str | None) -> JSONResponse:
        try:
            audio = await run_in_threadpool(decode_audio, path)
        except AudioDecodeError:
            return _err(415, "undecodable")
        if len(audio) < MIN_CLIP_S * SAMPLE_RATE:
            return _err(422, "too_short")
        result = await run_in_threadpool(analyze, audio, ctx, shruti or None)
        return JSONResponse(result.to_json())

    def _bad_shruti(shruti: str | None) -> bool:
        if not shruti:
            return False
        try:
            note_to_hz_near(shruti, 440.0)
            return False
        except ValueError:
            return True

    app.state.analyze_path = _analyze_path
    app.state.bad_shruti = _bad_shruti
    app.state.limiter = limiter
    app.state.client_key = _client_key
    app.state.settings = settings

    @app.get("/api/health")
    def health():
        return {"ok": True, "model_version": ctx.combine.model_version, "examples": len(ctx.index)}

    @app.post("/api/analyze")
    async def analyze_upload(request: Request, file: UploadFile = File(...), shruti: str | None = Form(None)):
        if not limiter.check(_client_key(request)):
            return _err(429, "rate_limited")
        if _bad_shruti(shruti):
            return _err(422, "bad_shruti")
        suffix = Path(file.filename or "clip").suffix[:10]
        with tempfile.TemporaryDirectory(prefix="raaga-") as tmp:
            path = Path(tmp) / f"upload{suffix}"
            size = 0
            with open(path, "wb") as out:
                while chunk := await file.read(CHUNK):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        return _err(413, "too_large")
                    out.write(chunk)
            return await _analyze_path(path, shruti)

    @app.get("/api/ragas")
    def ragas(q: str = ""):
        return [{"id": r.id, "name": r.name, "melakarta": r.melakarta, "parent": r.parent}
                for r in ctx.table.search(q, limit=20)]

    @app.get("/api/ragas/{raga_id}")
    def raga_detail(raga_id: str):
        r = ctx.table.ragas.get(raga_id)
        if r is None:
            return _err(404, "not_found")
        return {**r.to_json(), "example_count": ctx.index.count(r.id)}

    _register_youtube(app)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def api_not_found(rest: str):
        return _err(404, "not_found")

    if settings.static_dir is not None:
        static = Path(settings.static_dir).resolve()

        @app.get("/{path:path}")
        def spa(path: str):
            target = (static / path).resolve()
            if path and target.is_file() and target.is_relative_to(static):
                return FileResponse(target)
            return FileResponse(static / "index.html")

    return app


class YouTubeRequest(BaseModel):
    url: str
    start: float = 0.0
    shruti: str | None = None


def _register_youtube(app: FastAPI) -> None:
    @app.post("/api/analyze/youtube")
    async def analyze_youtube(request: Request, body: YouTubeRequest):
        st = app.state
        if not st.limiter.check(st.client_key(request)):
            return _err(429, "rate_limited")
        if st.bad_shruti(body.shruti):
            return _err(422, "bad_shruti")
        with tempfile.TemporaryDirectory(prefix="raaga-yt-") as tmp:
            try:
                path = await run_in_threadpool(fetch_youtube_segment, body.url, body.start, Path(tmp))
            except YouTubeInvalid:
                return _err(422, "bad_url")
            except YouTubeBlocked:
                return _err(502, "youtube_blocked")
            return await st.analyze_path(path, body.shruti)


def app_from_env() -> FastAPI:
    env = os.environ
    return create_app(Settings(
        store_dir=Path(env.get("RAAGA_STORE_DIR", "/data/store")),
        raga_table=Path(env.get("RAAGA_RAGA_TABLE", str(DEFAULT_TABLE))),
        params_path=Path(env["RAAGA_PARAMS"]) if env.get("RAAGA_PARAMS") else None,
        static_dir=Path(env["RAAGA_STATIC_DIR"]) if env.get("RAAGA_STATIC_DIR") else None,
    ))
