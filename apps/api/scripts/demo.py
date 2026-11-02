"""Local synthetic demo: real endpoints and PostgreSQL, rollback on shutdown, no AI calls."""

import argparse

import uvicorn
from fastapi.testclient import TestClient

from vaultline_api.demo.dataset import seed
from vaultline_api.demo.harness import isolated_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument(
        "--empty", action="store_true", help="Start without seeds for manual uploads"
    )
    args = parser.parse_args()
    with isolated_demo() as app:
        if not args.empty:
            with TestClient(app) as client:
                records = seed(client)
            for record in records.values():
                print(record["case"]["counterparty_name"], "→ /cases/" + record["case"]["id"])
        print("SYNTHETIC TEMPORARY DEMO: live AI disabled; no mock provider. Stop to roll back.")
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
