"""Verification-specific errors.

Only one is needed. Everything else reuses existing exceptions: ``CryptoError``,
``DatabaseError`` and subclasses, ``CertificateError`` and
``StoredCertificateError`` (imported from ``app.certificates.exceptions``; the
package ``__init__`` does not export it).
"""

from __future__ import annotations


class VerificationUnavailableError(Exception):
    """Authenticity cannot currently be established (maps to UNVERIFIABLE, HTTP 503).

    Raised when the signing key is unavailable or misconfigured, when the
    certificate was signed with a key other than the configured one, or when
    the certificate store is not available. The message is for server logs
    only and is never returned to clients.
    """
