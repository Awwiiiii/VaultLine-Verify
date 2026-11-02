"""Offline, redacted publication audit of worktree, index and reachable Git history.

Heuristic defense in depth, not proof of secret absence. Never prints matched content.
Does not stage files, alter Git configuration, write files or access the database/network.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "provider-token": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    "credential-url": re.compile(r"(?:postgres(?:ql)?(?:\+\w+)?|mysql|https?)://[^\s/:]+:[^\s@]+@"),
    "public-secret-name": re.compile(r"NEXT_PUBLIC_[A-Z_]*(?:API_KEY|TOKEN|PASSWORD|SECRET)\s*="),
}
ASSIGNMENT = re.compile(
    r"""(?i)\b(?:[A-Z_]*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|SECRET_KEY|CLIENT_SECRET))\b"""
    r"""\s*(?:=|:)\s*(?:"([^"\n]*)"|'([^'\n]*)'|([^\s,;)#]+))"""
)
SAFE_VALUES = {""}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def forbidden_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    if name.startswith(".env") and name != ".env.example":
        return True
    if any(
        p
        in {
            ".local",
            ".aws",
            ".ssh",
            "secrets",
            "node_modules",
            ".venv",
            "venv",
            "test-results",
            "playwright-report",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "backups",
            "dumps",
        }
        or p.startswith(".next")
        for p in parts[:-1]
    ):
        return True
    if name in {".netrc", ".pypirc", ".npmrc", "id_rsa", "id_ed25519", "credentials.json"}:
        return True
    suffixes = (
        ".db",
        ".sqlite",
        ".sqlite3",
        ".dump",
        ".backup",
        ".pem",
        ".key",
        ".p12",
        ".pfx",
        ".jks",
        ".keystore",
        ".log",
        ".pyc",
        ".tsbuildinfo",
        ".zip",
        ".tar",
        ".tar.gz",
        ".tgz",
        ".sql.gz",
    )
    return name.endswith(suffixes) or (
        name.endswith(".sql") and not path.startswith("apps/api/migrations/")
    )


def scan_content(path: str, data: bytes) -> list[tuple[str, int]]:
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return [("binary-review-required", 0)]
    findings = []
    for rule, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            if (
                rule == "credential-url"
                and path == "apps/api/alembic.ini"
                and match.group().endswith("://placeholder:placeholder@")
            ):
                continue  # Inert scaffold URL; migrations/env.py supplies validated settings.
            findings.append((rule, content.count("\n", 0, match.start()) + 1))
    for match in ASSIGNMENT.finditer(content):
        value = next(v for v in match.groups() if v is not None)
        # Allow only clear example/synthetic fixtures or runtime expressions, not arbitrary keys.
        if value in SAFE_VALUES or value.startswith(
            ("SYNTHETIC", "synthetic", "replace-with-", "<", "$", "{", "os.", "settings.", "self.")
        ):
            continue
        if path == "apps/api/tests/test_config.py" and value == "p@ss/word":
            continue  # Exact synthetic URL-escaping fixture, including the pre-existing index.
        if (
            match.group(3) is not None
            and path.endswith(".py")
            and (value in {"str", "None", "False", "True"} or value.startswith("quote_plus("))
        ):
            continue
        findings.append(("literal-credential-review", content.count("\n", 0, match.start()) + 1))
    return findings


def inspect_blob(scope: str, path: str, data: bytes) -> list[dict]:
    findings = [
        {"scope": scope, "path": path, "rule": rule, "line": line}
        for rule, line in scan_content(path, data)
    ]
    if forbidden_path(path):
        findings.append(
            {"scope": scope, "path": path, "rule": "private-or-generated-path", "line": 0}
        )
    return findings


def check_synthetic() -> list[dict]:
    """Verify explicit synthetic identity labels; manual review still matters."""
    directory = ROOT / "demo/synthetic"
    errors = []
    for path in directory.glob("*.csv"):
        rows = list(csv.reader(path.read_text().splitlines()))
        fields = dict(rows[1:])
        if rows[0] != ["field", "value"] or not path.name.startswith("SYNTHETIC-"):
            errors.append({"path": str(path.relative_to(ROOT)), "rule": "synthetic-schema"})
        identities = {
            "supplier_name",
            "buyer_name",
            "invoice_number",
            "po_number",
            "purchase_order_reference",
            "line_items.1.description",
        }
        if any(
            not value.startswith("SYNTHETIC") for key, value in fields.items() if key in identities
        ):
            errors.append({"path": str(path.relative_to(ROOT)), "rule": "synthetic-identity"})
    manifest = json.loads((directory / "manifest.json").read_text())
    if not manifest["label"].startswith("SYNTHETIC"):
        errors.append({"path": "demo/synthetic/manifest.json", "rule": "synthetic-label"})
    for scenario in manifest["scenarios"]:
        claim = scenario["claim"]
        if not scenario["name"].startswith("SYNTHETIC") or (
            claim
            and not all(claim[key].startswith("SYNTHETIC") for key in ("lender", "claim_reference"))
        ):
            errors.append({"path": "demo/synthetic/manifest.json", "rule": "synthetic-parties"})
    return errors


def main() -> int:
    findings = []
    paths = set(
        git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    ) - {""}
    for path in sorted(paths):
        file = ROOT / path
        if file.is_symlink():
            findings.append({"scope": "worktree", "path": path, "rule": "symlink-review"})
        elif file.is_file():
            findings.extend(inspect_blob("worktree", path, file.read_bytes()))
    index_entries = git("ls-files", "--stage", "-z").decode().split("\0")
    index_count = 0
    for entry in filter(None, index_entries):
        metadata, path = entry.split("\t", 1)
        mode, oid, stage = metadata.split()
        index_count += 1
        if mode not in {"100644", "100755"} or stage != "0":
            findings.append({"scope": "index", "path": path, "rule": "mode-or-conflict-review"})
        else:
            findings.extend(inspect_blob("index", path, git("cat-file", "blob", oid)))
    history_seen = set()
    for commit in git("rev-list", "--all").decode().splitlines():
        for entry in filter(None, git("ls-tree", "-r", "-z", commit).decode().split("\0")):
            metadata, path = entry.split("\t", 1)
            mode, kind, oid = metadata.split()
            if (oid, path) in history_seen:
                continue
            history_seen.add((oid, path))
            if kind == "blob":
                findings.extend(inspect_blob("history", path, git("cat-file", "blob", oid)))
    findings.extend(check_synthetic())
    probes = [
        ".env",
        "apps/api/.env",
        "apps/web/.env.local",
        ".local/evidence/example.csv",
        "backup.sql",
        "local.sqlite3",
        "local.db",
        "apps/web/tsconfig.tsbuildinfo",
        "apps/web/.next/example",
        "apps/web/.next-e2e/example",
        "apps/web/test-results/example",
        "private.key",
    ]
    for path in probes:
        result = subprocess.run(["git", "check-ignore", "--no-index", "-q", path], cwd=ROOT)
        if result.returncode != 0:
            findings.append({"scope": "ignore-probe", "path": path, "rule": "not-excluded"})
    print(
        json.dumps(
            {
                "worktree_files": len(paths),
                "index_files": index_count,
                "history_file_versions": len(history_seen),
                "findings": findings,
            },
            indent=2,
        )
    )
    print("Heuristic scan only; no secret values or matching lines printed.")
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())
