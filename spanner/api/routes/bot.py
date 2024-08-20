from fastapi import APIRouter, Request
from typing import Annotated, TYPE_CHECKING
from ..models.bot import Ping

if TYPE_CHECKING:
    from spanner.bot import CustomBridgeBot


api = APIRouter(prefix="/bot", tags=["Meta"])


@api.get("/ping", response_model=Ping)
async def ping(req: Request):
    """Gets the bot's discord gateway latency, in milliseconds"""
    return Ping(latency=round(req.app.bot.latency * 1000, 2))
