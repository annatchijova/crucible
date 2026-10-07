"""Offline Ed25519 trust-boundary probe; generates and deletes test keys.

This prototype demonstrates key possession and externally pinned-key checking.
It is not a production signer, identity provider, or semantic adjudicator.

Run from the repository root with:
    .venv/bin/python docs/evidence/reviewer_signature_trust_prototype.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def _run(openssl: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [openssl, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"OpenSSL operation failed: {result.stderr.strip()}")
    return result


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _key_fingerprint(openssl: str, public_key: Path) -> str:
    result = subprocess.run(
        [
            openssl,
            "pkey",
            "-pubin",
            "-in",
            str(public_key),
            "-outform",
            "DER",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("OpenSSL could not encode the test public key")
    return "sha256:" + hashlib.sha256(result.stdout).hexdigest()


def _verify(
    openssl: str, public_key: Path, payload_path: Path, signature_path: Path
) -> bool:
    result = _run(
        openssl,
        "pkeyutl",
        "-verify",
        "-rawin",
        "-pubin",
        "-inkey",
        str(public_key),
        "-in",
        str(payload_path),
        "-sigfile",
        str(signature_path),
        check=False,
    )
    return result.returncode == 0


def main() -> None:
    openssl = shutil.which("openssl")
    if openssl is None:
        raise SystemExit("openssl is required for this local probe")

    with TemporaryDirectory(prefix="crucible-review-signature-") as temp:
        root = Path(temp)
        key_paths: dict[str, tuple[Path, Path]] = {}
        for reviewer in ("a", "b"):
            private_key = root / f"{reviewer}-private.pem"
            public_key = root / f"{reviewer}-public.pem"
            _run(openssl, "genpkey", "-algorithm", "ED25519", "-out", str(private_key))
            _run(
                openssl,
                "pkey",
                "-in",
                str(private_key),
                "-pubout",
                "-out",
                str(public_key),
            )
            key_paths[reviewer] = (private_key, public_key)

        fingerprint_a = _key_fingerprint(openssl, key_paths["a"][1])
        fingerprint_b = _key_fingerprint(openssl, key_paths["b"][1])
        trusted_fingerprints = {fingerprint_a}

        statement = {
            "schema_version": "crucible-coverage-review/v1",
            "source_ir_digest": "sha256:fixture-ir",
            "source_audit_digest": "sha256:fixture-audit",
            "skill": "synthetic-skill",
            "rule_id": "rule-0001",
            "check_id": "check-0001",
            "review_criterion": "coverage-criterion/v1",
            "review_outcome": "COVERS",
            "reviewer_key_id": fingerprint_a,
        }
        payload = root / "attestation.json"
        signature_a = root / "attestation-a.sig"
        payload.write_bytes(_canonical_bytes(statement))
        _run(
            openssl,
            "pkeyutl",
            "-sign",
            "-rawin",
            "-inkey",
            str(key_paths["a"][0]),
            "-in",
            str(payload),
            "-out",
            str(signature_a),
        )

        pinned_accepts = (
            statement["reviewer_key_id"] in trusted_fingerprints
            and _verify(openssl, key_paths["a"][1], payload, signature_a)
        )

        attacker_statement = {**statement, "reviewer_key_id": fingerprint_b}
        attacker_payload = root / "attacker-attestation.json"
        attacker_signature = root / "attacker-b.sig"
        attacker_payload.write_bytes(_canonical_bytes(attacker_statement))
        _run(
            openssl,
            "pkeyutl",
            "-sign",
            "-rawin",
            "-inkey",
            str(key_paths["b"][0]),
            "-in",
            str(attacker_payload),
            "-out",
            str(attacker_signature),
        )
        # This is the required trust check. A valid signature alone is not enough.
        untrusted_key_rejected = (
            fingerprint_b not in trusted_fingerprints
            and not _verify(openssl, key_paths["a"][1], attacker_payload, attacker_signature)
        )
        # Negative control: if the artifact supplies its own key, B's signature
        # is cryptographically valid. The key is not thereby authorized.
        self_supplied_key_verifies = _verify(
            openssl, key_paths["b"][1], attacker_payload, attacker_signature
        )

        tampered_payload = root / "tampered-attestation.json"
        tampered_statement = {**statement, "source_ir_digest": "sha256:other-ir"}
        tampered_payload.write_bytes(_canonical_bytes(tampered_statement))
        source_change_rejected = not _verify(
            openssl, key_paths["a"][1], tampered_payload, signature_a
        )

    output = {
        "experiment": "reviewer-signature-trust-prototype/v1",
        "scope": "cryptographic binding and local key allowlist only",
        "pinned_key_signature_accepted": pinned_accepts,
        "untrusted_key_rejected_by_allowlist": untrusted_key_rejected,
        "self_supplied_key_signature_is_valid": self_supplied_key_verifies,
        "changed_source_digest_rejected": source_change_rejected,
        "identity_or_authority_proven": False,
        "semantic_correctness_proven": False,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    if not all((pinned_accepts, untrusted_key_rejected,
                self_supplied_key_verifies, source_change_rejected)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
