"""TEST ONLY: loopback browser fixture, real PostgreSQL, explicit mock AI, no external HTTP."""

import httpx
import uvicorn

from vaultline_api.demo.harness import isolated_demo
from vaultline_api.investigations.providers import MockAIProvider, get_provider


def denied(*args, **kwargs):
    raise AssertionError("External HTTP is disabled in browser tests")


def main():
    httpx.HTTPTransport.handle_request = denied
    with isolated_demo() as app:
        app.dependency_overrides[get_provider] = lambda: MockAIProvider()
        print("TEST ONLY — MockAIProvider explicitly injected; PostgreSQL rolls back on exit.")
        uvicorn.run(app, host="127.0.0.1", port=8102, log_level="warning")


if __name__ == "__main__":
    main()
