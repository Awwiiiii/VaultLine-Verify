# VaultLine Verify

## Mission

VaultLine is financial trust and control infrastructure. VaultLine Verify is its first module, helping lenders and financial institutions verify receivables and supporting financial evidence before financing decisions. The product ingests financial documents, normalizes data, checks evidence across documents, detects duplicate financing claims and discrepancies, preserves provenance, and provides evidence-based risk scoring and decision support.

## Architecture

Build a modular monolith. Keep domain boundaries clear and modules cohesive; avoid unnecessary microservices, infrastructure, and distributed complexity.

- Frontend: Next.js, TypeScript, Tailwind CSS.
- Backend: Python 3.12, FastAPI, Pydantic v2.
- Persistence: PostgreSQL, SQLAlchemy, Alembic.
- Local infrastructure: Docker Compose.
- Testing: Pytest and appropriate frontend tests.
- AI: provider-independent interfaces, with Meta as the first provider. Keep provider-specific code behind adapters so another provider can be added without changing verification domain logic.

## Coding conventions

- Prefer clear, typed, small modules with explicit responsibilities and interfaces.
- Validate input at system boundaries. Use Pydantic schemas for API and model-output boundaries; do not treat type annotations as runtime validation.
- Keep API, domain, persistence, and provider integration concerns separated.
- Make errors explicit and avoid logging credentials, personal information, or raw sensitive financial documents.
- Document non-obvious financial and verification rules near their implementation.
- Label all synthetic demonstration data conspicuously as synthetic. Never present it as real customer, lender, or transaction data.

## Financial correctness and verification

- Use `Decimal` for every financial amount and monetary calculation. Never use binary floating-point for money. Define currency and rounding behavior explicitly at relevant boundaries.
- Preserve source values and their provenance: document identity, location within the document when available, extraction/normalization steps, and relevant timestamps. Do not silently overwrite source evidence with normalized values.
- Every verification result, discrepancy, duplicate-claim finding, and risk factor must be traceable to supporting evidence. State when evidence is missing, ambiguous, or contradictory; do not present an unsupported conclusion as verified.
- Keep deterministic financial checks and decisions separate from AI-generated recommendations. AI may assist investigation and decision support, but must not silently alter deterministic outcomes or be represented as authoritative verification.
- Treat uploaded documents and all model outputs as untrusted input. Defend against malformed, adversarial, or instruction-bearing content; never execute document or model instructions as code or policy.
- Strictly validate AI outputs against bounded schemas and allowed values. Reject invalid, incomplete, or out-of-range outputs; do not coerce them into trusted decisions. Preserve enough provenance to audit AI-assisted findings.

## Security and sensitive data

- Never commit credentials, access tokens, private keys, production data, or local secret files. Read secrets from environment/configuration or an approved secret store; provide safe placeholders in `.env.example`.
- Apply least privilege, input validation, and secure defaults. Protect sensitive data in transit and at rest in line with the deployment environment.
- Minimize collection, retention, and exposure of personal and financial data. Redact sensitive values from logs, exceptions, fixtures, and test output.
- Do not send sensitive data to an AI provider unless the integration and data handling are explicitly approved for that use.

## Testing requirements

- Add or update tests for meaningful behavior, especially financial arithmetic, validation boundaries, evidence provenance, duplicate-claim detection, discrepancy handling, and AI-output rejection paths.
- Use deterministic tests and synthetic fixtures; mark synthetic fixtures clearly. Never rely on real customer financial data in tests.
- Run relevant backend and frontend checks for changes and report any checks that could not be run. Tests must cover failure cases as well as successful paths.
- Test that provider adapters conform to the shared provider-independent interface.
