"""Synthetic-only regression tests for the redacted release audit."""

import unittest

import release_check as audit


class ReleaseCheckTests(unittest.TestCase):
    def test_flags_sensitive_paths_in_index_even_when_ignored(self):
        for path in (
            ".env",
            "apps/api/.env.local",
            ".local/evidence/source.csv",
            "backup.sql",
            "data.sqlite3",
            "apps/web/.next/server.js",
            "private.key",
        ):
            with self.subTest(path=path):
                self.assertTrue(audit.forbidden_path(path))

    def test_keeps_examples_and_source_migrations(self):
        for path in (
            ".env.example",
            "apps/api/.env.example",
            "apps/api/migrations/versions/0001.py",
            "apps/api/migrations/source.sql",
        ):
            self.assertFalse(audit.forbidden_path(path))

    def test_detects_key_shapes_without_disclosing_values(self):
        tokens = (
            "gh" + "p_" + "A" * 36,
            "sk" + "-" + "A" * 30,
            "AK" + "IA" + "A" * 16,
            "xox" + "b-" + "a" * 30,
        )
        for token in tokens:
            findings = audit.inspect_blob("index", "sample.txt", token.encode())
            self.assertTrue(findings)
            self.assertTrue(all(token not in str(finding) for finding in findings))

    def test_checks_arbitrary_literal_provider_keys(self):
        content = ("MODEL_" + "API_KEY" + '="unlabeled-credential-example"').encode()
        self.assertTrue(audit.scan_content("config.py", content))
        content = ("MODEL_" + "API_KEY" + '="SYNTHETIC-TEST-KEY"').encode()
        self.assertEqual(audit.scan_content("config.py", content), [])

    def test_only_exact_inert_url_placeholder_is_exempt(self):
        value = (
            "postgresql+psycopg" + "://" + "placeholder:placeholder" + "@localhost/db"
        ).encode()
        self.assertEqual(audit.scan_content("apps/api/alembic.ini", value), [])
        self.assertTrue(audit.scan_content("other.txt", value))

    def test_binary_content_requires_review(self):
        self.assertEqual(
            audit.scan_content("artifact.bin", b"\xff\xfe"), [("binary-review-required", 0)]
        )

    def test_shared_demo_has_explicit_synthetic_labels(self):
        self.assertEqual(audit.check_synthetic(), [])


if __name__ == "__main__":
    unittest.main()
