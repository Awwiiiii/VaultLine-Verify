"""Opt-in single Baseten request using synthetic evidence; never collected by pytest."""

import argparse
from uuid import uuid4

from vaultline_api.investigations.baseten import BasetenAIProvider, ProviderConfiguration
from vaultline_api.investigations.contracts import (
    EvidenceEntry,
    EvidencePackage,
    OutputValidationError,
    validate_output,
)
from vaultline_api.investigations.diagnostics import error_stage
from vaultline_api.investigations.providers import ERRORS, ProviderError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authorize-live",
        action="store_true",
        help="Explicitly authorize one real, potentially billable Baseten API call",
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
        config = ProviderConfiguration()
        output = BasetenAIProvider(
            max_tokens=config.baseten_max_tokens, output_mode=config.baseten_output_mode
        ).generate(package)
        validate_output(output, package)
    except Exception as exc:
        code = "configuration_or_validation_failure"
        if isinstance(exc, ProviderError) and exc.code in ERRORS:
            code = exc.code
        elif isinstance(exc, OutputValidationError) and "baseten_" + exc.code in ERRORS:
            code = "baseten_" + exc.code
        print(
            "Smoke test failed:",
            code,
            "stage=" + (error_stage(code) or "configuration_or_transport"),
        )
        raise SystemExit(1) from None
    print(
        "One live Baseten request (meta-models/muse-spark-open) "
        "passed local schema and evidence validation. No database records created."
    )


if __name__ == "__main__":
    main()
