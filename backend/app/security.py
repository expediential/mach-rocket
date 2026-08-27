"""Practical, intentionally limited local security checks."""
from __future__ import annotations

import re
from pathlib import Path

from .models import SecurityFinding

SECRET_PATTERNS = {"Private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Likely API token": re.compile(r"(?i)(?:api[_-]?key|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]")}


def scan_text(name: str, content: str) -> list[SecurityFinding]:
    """Flag probable secrets in supplied text; never execute supplied content."""
    findings = []
    for title, pattern in SECRET_PATTERNS.items():
        if pattern.search(content):
            findings.append(SecurityFinding(id=f"sec-{len(findings) + 1}", title=title, severity="HIGH", status="OPEN", detail=f"Potential secret detected in {Path(name).name}. Review and rotate if real."))
    return findings


def demo_findings() -> list[SecurityFinding]:
    """Return the demo security evidence shown in the starter project."""
    return [SecurityFinding(id="SEC-001", title="Malformed packet rejected", severity="LOW", status="RESOLVED", detail="Schema validation rejected a packet with an invalid temperature value; no source data was changed."), SecurityFinding(id="SEC-002", title="No hard-coded production credentials", severity="INFO", status="PASS", detail="Demo integrity key is explicitly development-only and is not a production credential.")]
