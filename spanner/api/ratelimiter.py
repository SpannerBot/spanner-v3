import time

__all__ = ("Bucket", "Ratelimiter")


class Bucket:
    # key: str
    # """A unique key for this endpoint"""
    # limit: int
    # """The maximum amount of requests this endpoint can receive in the given time window"""
    # remaining: int
    # """The amount of requests remaining in the current time window"""
    # reset: float
    # """The unix timestamp in seconds at which the current time window will reset"""
    # window: int | float | None = None
    # """For internal ratelimiting, the time window in seconds"""
    # external_key: str | None = None
    # """The key to use when ratelimiting against an external service"""

    def __init__(
        self,
        key: str,
        limit: int,
        remaining: int,
        reset: float,
        window: int | float | None = None,
        external_key: str | None = None,
    ):
        self.key = key
        self.limit = limit
        self.remaining = remaining
        self.reset = reset
        self.window = window
        self.external_key = external_key

    @property
    def reset_after(self) -> float:
        """The amount of seconds until the current time window resets"""
        return self.reset - time.time()

    @property
    def exhausted(self) -> bool:
        """Whether the bucket is exhausted, and another request would throw a 429"""
        return self.remaining <= 0 < self.reset_after

    def renew(self):
        """Renew the bucket, setting the remaining requests to the limit"""
        self.remaining = self.limit
        self.reset = time.time() + self.window

    def renew_if_not_expired(self):
        """Renew the bucket if it is not expired"""
        if time.time() > self.reset:
            self.renew()

    def generate_ratelimit_headers(self) -> dict[str, str]:
        """
        Generates headers suitable to return in a 429 response
        """
        return {
            "X-Ratelimit-Bucket": self.key,
            "X-Ratelimit-Limit": str(self.limit),
            "X-Ratelimit-Remaining": str(self.remaining),
            "X-Ratelimit-Reset": str(self.reset),
            "Retry-After": str(self.reset_after),
        }

    @classmethod
    def from_discord_headers(cls, headers: dict[str, str], *, key: str):
        """Create a bucket from a set of headers"""
        return cls(
            key=key,
            limit=int(headers["X-Ratelimit-Limit"]),
            remaining=int(headers["X-Ratelimit-Remaining"]),
            reset=float(headers["X-Ratelimit-Reset"]),
            external_key=headers["X-Ratelimit-Bucket"],
        )


class Ratelimiter:
    def __init__(self):
        self.buckets: dict[str, Bucket] = {}

    def __repr__(self):
        return f"<Ratelimiter buckets={self.buckets}>"

    def get_bucket(self, key: str) -> Bucket | None:
        """Get the bucket for a given key"""
        b = self.buckets.get(key)
        if b:
            return b
        for bucket in self.buckets.values():
            if bucket.external_key == key:
                return bucket

    def from_discord_headers(self, headers: dict[str, str], *, key: str):
        """Create a bucket from a set of headers"""
        bucket = Bucket.from_discord_headers(headers, key=key)
        self.buckets[bucket.key] = bucket
        return bucket
