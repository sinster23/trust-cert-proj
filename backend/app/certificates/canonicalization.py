"""Deterministic canonical bytes for certificates (M5).

Canonical format, schema v1
---------------------------
* A JSON object containing exactly the fields in ``CERTIFICATE_FIELDS``
  (``schema_version`` included; signature metadata and status never are).
* Keys sorted lexicographically; no whitespace (``separators=(",", ":")``).
* Every value is a string, already normalized by the domain model
  (NFC text, collapsed whitespace, strict YYYY-MM-DD dates).
* ``ensure_ascii=False`` and UTF-8 encoding, so the bytes do not depend on
  escape-sequence choices.
* No optional or null fields exist in v1; a missing field is an error.

The output is ``bytes`` and can be passed straight to
``CryptoService.sign`` / ``verify_signature``. Any change to these rules needs
a new ``schema_version``.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .exceptions import CanonicalizationError
from .models import CERTIFICATE_FIELDS, Certificate


def canonicalize(certificate: Certificate | Mapping[str, Any]) -> bytes:
    """Return the deterministic bytes to sign for a certificate.

    Accepts a ``Certificate`` or a mapping (e.g. stored/submitted data), which
    is re-validated through the domain model so unvalidated data is never
    serialized.
    """
    if isinstance(certificate, Mapping):
        certificate = Certificate.from_dict(dict(certificate))
    if not isinstance(certificate, Certificate):
        raise CanonicalizationError("Unsupported certificate type")

    data = certificate.to_dict()
    if set(data) != set(CERTIFICATE_FIELDS):  # defensive; model guarantees this
        raise CanonicalizationError("Certificate fields do not match the schema")
    try:
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError("Certificate could not be serialized") from exc