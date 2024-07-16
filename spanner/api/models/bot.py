from pydantic import BaseModel


class Ping(BaseModel):
    latency: float
