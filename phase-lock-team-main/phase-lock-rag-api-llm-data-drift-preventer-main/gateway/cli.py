import os

import uvicorn


def main() -> None:
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", "8000"))
    reload_mode = os.getenv("GATEWAY_RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("gateway.main:app", host=host, port=port, reload=reload_mode)


if __name__ == "__main__":
    main()
