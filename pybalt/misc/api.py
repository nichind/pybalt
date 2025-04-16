from .. import core, VERSION
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from asyncio import run, sleep, create_task
import uvicorn


app = FastAPI()
manager = core.wrapper.InstanceManager()
config = core.config.Config()


@app.get("/")
async def root(request: Request):
    return {
        "message": "Welcome to the https://github.com/nichind/pybalt api, you can use it just like you would use any normal cobalt instance, the response would be always from the fastest instance to answer to the request",
        "version": VERSION,
        "instance_count": len(manager.all_instances),
    }


@app.post("/")
async def post(request: Request):
    data = await request.json()
    url = data.get("url", None)
    if url is None:
        return {"error": "URL not provided"}
    del data["url"]
    return JSONResponse(await (await manager.first_tunnel(url, **data)).json())


@app.on_event("startup")
async def startup_event():
    """Start background tasks when the API starts."""
    create_task(update_instances())


async def update_instances():
    """Periodically update the stored_instances list with current instances."""
    while True:
        try:
            await manager.get_instances()
        except Exception as e:
            print(f"Error updating instances: {e}")

        # Get instance list update period from config
        update_period = config.get_as_number("update_period", 60, "api")

        await sleep(update_period)


def run_api(port=None, **kwargs):
    """Run the FastAPI application on the specified port or from config."""
    # Use provided port, or get it from kwargs, or from config, or default to 8000
    if port is None:
        port = config.get_as_number("port", 8009, "api")

    # Run the API server
    uvicorn.run(app, host="0.0.0.0", port=port)
