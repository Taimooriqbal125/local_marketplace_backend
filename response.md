import uvicorn
from fastapi import Depends, FastAPI
from pyrate_limiter import Duration, Limiter, Rate

from fastapi_limiter.depends import RateLimiter

app = FastAPI()

@app.get(
    "/",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(2, Duration.SECOND * 5))))],
)
async def index():
    return {"msg": "Hello World"}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)


    from fastapi import FastAPI
from pyrate_limiter import Duration, Limiter, Rate

from fastapi_limiter.middleware import RateLimiterMiddleware

app = FastAPI()

app.add_middleware(
    RateLimiterMiddleware,
    limiter=Limiter(Rate(2, Duration.SECOND * 5)),
)


@app.get("/")
async def index():
    return {"msg": "Hello World"}