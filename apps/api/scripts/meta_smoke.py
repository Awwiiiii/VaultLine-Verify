"""Opt-in single Meta request using synthetic evidence; never collected by pytest."""

import argparse
from uuid import uuid4

from vaultline_api.investigations.contracts import EvidenceEntry, EvidencePackage, validate_output
from vaultline_api.investigations.providers import MetaAIProvider, ProviderError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authorize-live",
        action="store_true",
        help="Explicitly authorize one real, potentially billable Meta API call",
    )
    args = parser.parse_args()
    if not args.authorize_live:
        parser.error("No request made. Explicit --authorize-live is required.")
    package = EvidencePackage(
        case_id=str(uuid4()),
        captured_at="2026-11-03T00:00:00Z",
        verification_run_id=None,
        verification_created_at=None,
        entries=[
            EvidenceEntry(
                id="synthetic:coverage",
                kind="unknown",
                text="SYNTHETIC smoke test: no financial evidence supplied.",
                document_ids=[],
                claim_ids=[],
                case_ids=[],
                provenance=[],
            )
        ],
    )
    try:
        output = MetaAIProvider().generate(package)
        validate_output(output, package)
    except (ProviderError, ValueError) as exc:
        print(
            "Smoke test failed:", exc.code if isinstance(exc, ProviderError) else "invalid_output"
        )
        raise SystemExit(1) from None
    print("One live Meta request passed local validation. No database records created.")


if __name__ == "__main__":
    main()
