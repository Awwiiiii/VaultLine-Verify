"""Transparent classification of existing findings; no money calculation or AI dependency."""

from vaultline_api.risk.contracts import Indicator, RiskAssessment, RiskInputs, Source

CLAIM_RULES = {
    "potential_competing_claims": (
        "potential_claim_conflict",
        "Potential competing recorded claims",
    ),
    "confirmed_duplicate_records": ("duplicate_assertions", "Duplicate registry assertions"),
    "aggregate_exceeds_invoice": (
        "aggregate_claim_excess",
        "Recorded active amounts exceed invoice total",
    ),
    "insufficient_evidence": ("insufficient_evidence", "Claim evidence is insufficient"),
    "no_conflict_found": ("no_recorded_claim_conflict", "No claim conflict found in recorded data"),
}
REVIEW_CATEGORIES = {
    "discrepancy",
    "potential_claim_conflict",
    "aggregate_claim_excess",
    "duplicate_assertions",
}


def assess(inputs: RiskInputs) -> RiskAssessment:
    """Identical validated inputs yield identical ordered indicators and source references."""
    sources: list[Source] = []
    indicators: list[Indicator] = []

    def source(identifier, kind, payload):
        sources.append(Source(id=identifier, kind=kind, payload=payload))
        return identifier

    def indicator(category, title, explanation, refs):
        indicators.append(
            Indicator(
                id=f"indicator:{len(indicators)}",
                category=category,
                title=title,
                explanation=explanation,
                source_refs=refs,
            )
        )

    coverage = source(
        "verification_coverage",
        "verification_coverage",
        {
            "case_id": inputs.case_id,
            "freshness": inputs.freshness,
            "saved_document_fingerprint": inputs.saved_document_fingerprint,
            "current_document_fingerprint": inputs.current_document_fingerprint,
        },
    )
    if inputs.freshness != "current":
        indicator(
            "insufficient_evidence",
            "No current verification coverage",
            "No saved verification exists. Run deterministic verification."
            if inputs.freshness == "missing"
            else (
                "Verification dataset evidence changed. Rerun verification; "
                "saved findings remain historical."
            ),
            [coverage],
        )
    run = inputs.verification
    if run is not None:
        run_ref = source(
            "verification:" + run.id,
            "verification_run",
            run.model_dump(mode="json", exclude={"findings"}),
        )
        for position, finding in enumerate(run.findings):
            ref = source(
                f"verification:{run.id}:finding:{position}",
                "verification_finding",
                finding.model_dump(mode="json"),
            )
            if finding.outcome == "discrepancy":
                indicator(
                    "discrepancy",
                    f"Recorded discrepancy: {finding.rule_id}",
                    (
                        "Investigate the cited deterministic discrepancy and source evidence. "
                        "It does not establish fraud or legal rights."
                    ),
                    [ref],
                )
            elif finding.outcome == "insufficient_evidence" or (
                finding.outcome == "not_applicable" and finding.mandatory
            ):
                indicator(
                    "insufficient_evidence",
                    f"Unresolved evidence: {finding.rule_id}",
                    (
                        "The cited check could not be established. "
                        "Missing evidence is not evidence of fraud."
                    ),
                    [ref],
                )
            elif finding.outcome == "not_applicable":
                indicator(
                    "unchecked_comparison",
                    f"Comparison not performed: {finding.rule_id}",
                    "This optional comparison was not performed; no match is asserted.",
                    [ref],
                )
        # Fail conservatively even if a historical run has no detailed finding payloads.
        if run.outcome != "passed" and not any(
            f.outcome in {"discrepancy", "insufficient_evidence"} for f in run.findings
        ):
            indicator(
                "insufficient_evidence",
                "Saved verification is not a complete pass",
                "The saved run does not establish complete passing document checks.",
                [run_ref],
            )
        if not run.findings:
            indicator(
                "insufficient_evidence",
                "Verification findings are unavailable",
                "The saved summary has no supporting check findings.",
                [run_ref],
            )
    for claim in inputs.claims:
        source("claim:" + claim.id, "claim_assertion", claim.model_dump(mode="json"))
    for position, conflict in enumerate(inputs.claim_conflicts):
        ref = source(
            f"claim_conflict:{position}", "claim_conflict", conflict.model_dump(mode="json")
        )
        refs = [ref] + ["claim:" + identifier for identifier in conflict.claim_ids]
        category, title = CLAIM_RULES[conflict.category]
        indicator(
            category,
            title,
            (
                "The cited finding describes recorded assertions only. "
                "It does not prove financing, ownership, fraud or absence of external claims."
            ),
            refs,
        )
    if not inputs.claim_conflicts:
        indicator(
            "insufficient_evidence",
            "Claim conflict coverage unavailable",
            "No deterministic claim-conflict result was supplied.",
            [coverage],
        )
    scope_ref = source(
        "scope", "scope_limitation", {"case_id": inputs.case_id, "scope": inputs.scope}
    )
    indicator(
        "unknown_external_financing",
        "External financing remains unknown",
        "Only recorded VaultLine evidence is assessed; external financing has not been verified.",
        [scope_ref],
    )
    known = {s.id for s in sources}
    if any(ref not in known for item in indicators for ref in item.source_refs):
        raise ValueError("Risk indicator references unsupported evidence")
    categories = {item.category for item in indicators}
    status = (
        "review_findings_present"
        if categories & REVIEW_CATEGORIES
        else "insufficient_evidence"
        if "insufficient_evidence" in categories
        else "no_recorded_discrepancy"
    )
    return RiskAssessment(
        case_id=inputs.case_id,
        assessment_status=status,
        indicators=indicators,
        sources=sources,
        input_snapshot=inputs,
    )
