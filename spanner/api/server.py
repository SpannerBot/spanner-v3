from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.config import router as config_router
from .routes.discord_api import router as discord_router
from .routes.oauth2 import router as oauth2_router
from .vars import CORS_ALLOW_CREDENTIALS, CORS_ALLOW_HEADERS, CORS_ALLOW_METHODS, CORS_ALLOW_ORIGINS

app = FastAPI(debug=True, title="Spanner API", version="3.0.0a1.dev1")
app.include_router(oauth2_router, prefix="/oauth2")
app.include_router(discord_router, prefix="/_discord")
app.include_router(config_router, prefix="/config")

if CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:1237", "http://localhost:3000"],
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
    )
