"""Persist inputs before calling a provider; only validated output becomes a report."""

from uuid import UUID

from sqlalchemy.orm import Session

from vaultline_api.api.routes.cases import require_case
from vaultline_api.db.models import Investigation
from vaultline_api.investigations.contracts import OutputValidationError, validate_output
from vaultline_api.investigations.diagnostics import error_stage
from vaultline_api.investigations.evidence import build_evidence
from vaultline_api.investigations.providers import ERRORS, AIProvider, ProviderError


def response(record: Investigation, detail: bool = True) -> dict:
    result = {
        "id": str(record.id),
        "case_id": str(record.case_id),
        "provider": record.provider,
        "model": record.model,
        "status": record.status,
        "error_code": record.error_code,
        "error": ERRORS.get(record.error_code),
        "error_stage": error_stage(record.error_code),
        "created_at": record.created_at.isoformat(),
    }
    if detail:
        result.update(evidence_snapshot=record.evidence_snapshot, output=record.output)
    return result


def investigate(db: Session, case_id: UUID, provider: AIProvider) -> dict:
    with db.begin():
        require_case(db, case_id)
        try:
            package = build_evidence(db, case_id)
        except ProviderError as exc:
            record = Investigation(
                case_id=case_id,
                provider=provider.name,
                model=provider.model,
                evidence_snapshot={"error": exc.code},
                status="failed",
                error_code=exc.code,
            )
            db.add(record)
            db.flush()
            return response(record)
        record = Investigation(
            case_id=case_id,
            provider=provider.name,
            model=provider.model,
            evidence_snapshot=package.model_dump(mode="json"),
            status="pending",
        )
        db.add(record)
        db.flush()
        identifier = record.id
    output, error = None, None
    try:
        raw = provider.generate(package)
        if not isinstance(raw, str) or len(raw.encode()) > 100000:
            raise ValueError("Invalid output")
        output = validate_output(raw, package).model_dump(mode="json")
    except ProviderError as exc:
        error = exc.code if exc.code in ERRORS else "provider_error"
    except OutputValidationError as exc:
        code = "baseten_" + exc.code
        error = code if provider.name == "baseten" and code in ERRORS else "invalid_output"
    except (ValueError, TypeError):
        error = "invalid_output"
    except Exception:
        # Provider exceptions can contain credentials or evidence; never persist their text.
        error = "provider_error"
    with db.begin():
        record = db.get(Investigation, identifier)
        record.output, record.error_code = output, error
        record.status = "failed" if error else "completed"
        db.flush()
        return response(record)
