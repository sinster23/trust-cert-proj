from __future__ import annotations

import json
import re

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.certificates import (
    SCHEMA_VERSION,
    CanonicalizationError,
    Certificate,
    CertificateIssueRequest,
    CertificateValidationError,
    UnsupportedSchemaVersionError,
    canonicalize,
    generate_certificate_id,
    parse_issue_request,
)
from app.certificates.models import CERTIFICATE_FIELDS
from app.crypto.signatures import sign_bytes, verify_bytes

VALID = dict(
    student_id="CS2021-001",
    student_name="Asha Rao",
    institution="Example Institute of Technology",
    degree="Bachelor of Technology",
    field_of_study="Computer Science and Engineering",
    graduation_date="2025-06-15",
)


def make(**overrides) -> Certificate:
    data = {**VALID, "issue_date": "2025-07-01", **overrides}
    return Certificate.issue(**data)


# ---- IDs ---------------------------------------------------------------

def test_certificate_id_format_and_uniqueness():
    ids = {generate_certificate_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(re.fullmatch(r"CERT-[0-9a-f]{32}", i) for i in ids)


def test_issue_generates_id_and_sets_version():
    cert = make()
    assert cert.certificate_id.startswith("CERT-")
    assert cert.schema_version == SCHEMA_VERSION
    assert make().certificate_id != cert.certificate_id


def test_client_cannot_supply_id_or_issue_date():
    for extra in ("certificate_id", "issue_date", "schema_version"):
        with pytest.raises(CertificateValidationError):
            parse_issue_request({**VALID, extra: "x"})


def test_certificate_is_immutable():
    cert = make()
    with pytest.raises(Exception):
        cert.student_name = "Someone Else"  # type: ignore[misc]


# ---- validation --------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    ["2025-6-15", "15-06-2025", "2025/06/15", "2025-02-30", "2025-13-01",
     " 2025-06-15", "2025-06-15T00:00:00", "", None, 20250615],
)
def test_bad_graduation_dates_rejected(bad):
    with pytest.raises(CertificateValidationError) as err:
        make(graduation_date=bad)
    assert err.value.field == "graduation_date"


def test_issue_date_before_graduation_rejected():
    with pytest.raises(CertificateValidationError) as err:
        make(issue_date="2025-06-14")
    assert err.value.field == "issue_date"


def test_issue_date_equal_to_graduation_allowed():
    assert make(issue_date="2025-06-15").issue_date == "2025-06-15"


@pytest.mark.parametrize("field", list(VALID))
@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_required_fields_reject_empty_and_wrong_type(field, bad):
    with pytest.raises(CertificateValidationError):
        make(**{field: bad})


def test_text_length_limit():
    with pytest.raises(CertificateValidationError):
        make(student_name="a" * 201)


def test_control_characters_rejected():
    with pytest.raises(CertificateValidationError):
        make(student_name="Asha\x00Rao")


@pytest.mark.parametrize("bad", ["-abc", "a b", "a;b", "a" * 65, "<script>"])
def test_bad_student_ids(bad):
    with pytest.raises(CertificateValidationError) as err:
        make(student_id=bad)
    assert err.value.field == "student_id"


def test_unsupported_schema_version():
    with pytest.raises(UnsupportedSchemaVersionError):
        Certificate(certificate_id=generate_certificate_id(),
                    issue_date="2025-07-01", schema_version="9.9", **VALID)


def test_bad_certificate_id_rejected():
    with pytest.raises(CertificateValidationError):
        Certificate(certificate_id="CERT-123", issue_date="2025-07-01", **VALID)


def test_issue_request_schema_rejects_unknown_and_missing():
    with pytest.raises(CertificateValidationError):
        parse_issue_request({**VALID, "role": "ADMIN"})
    partial = dict(VALID)
    partial.pop("degree")
    with pytest.raises(CertificateValidationError) as err:
        parse_issue_request(partial)
    assert err.value.field == "degree"


def test_issue_request_to_certificate():
    req = CertificateIssueRequest(**VALID)
    cert = req.to_certificate(issue_date="2025-07-01")
    assert cert.student_name == "Asha Rao"
    assert cert.certificate_id.startswith("CERT-")


# ---- normalization -----------------------------------------------------

def test_whitespace_and_unicode_normalization():
    composed = make(student_name="José Ñandú")
    decomposed = Certificate(
        **{**composed.to_dict(), "student_name": "  Jose\u0301   N\u0303andu\u0301 "}
    )
    assert decomposed.student_name == composed.student_name
    assert canonicalize(decomposed) == canonicalize(composed)


# ---- canonicalization --------------------------------------------------

def test_canonical_output_is_bytes_with_exact_fields():
    out = canonicalize(make())
    assert isinstance(out, bytes)
    parsed = json.loads(out)
    assert set(parsed) == set(CERTIFICATE_FIELDS)
    assert parsed["schema_version"] == SCHEMA_VERSION


def test_canonical_is_compact_sorted_utf8():
    cert = make(student_name="Zoë Müller")
    out = canonicalize(cert)
    text = out.decode("utf-8")
    assert " " not in text.replace("Zoë Müller", "").replace(
        "Example Institute of Technology", "").replace(
        "Bachelor of Technology", "").replace(
        "Computer Science and Engineering", "")
    keys = [m for m in re.findall(r'"([a-z_]+)":', text)]
    assert keys == sorted(keys)
    assert "Zoë Müller" in text  # not \u-escaped


def test_canonical_known_vector_is_stable():
    cert = Certificate(
        certificate_id="CERT-" + "0" * 32,
        issue_date="2025-07-01",
        **VALID,
    )
    expected = (
        '{"certificate_id":"CERT-00000000000000000000000000000000",'
        '"degree":"Bachelor of Technology",'
        '"field_of_study":"Computer Science and Engineering",'
        '"graduation_date":"2025-06-15",'
        '"institution":"Example Institute of Technology",'
        '"issue_date":"2025-07-01",'
        '"schema_version":"1.0",'
        '"student_id":"CS2021-001",'
        '"student_name":"Asha Rao"}'
    ).encode("utf-8")
    assert canonicalize(cert) == expected


def test_same_data_same_bytes_regardless_of_input_order():
    cert = make()
    d = cert.to_dict()
    reordered = dict(reversed(list(d.items())))
    assert canonicalize(Certificate.from_dict(reordered)) == canonicalize(cert)
    assert canonicalize(reordered) == canonicalize(cert)


def test_any_field_change_changes_bytes():
    base = make()
    base_bytes = canonicalize(base)
    for name, new in [
        ("student_name", "Different Name"),
        ("degree", "Master of Technology"),
        ("graduation_date", "2025-06-16"),
        ("student_id", "CS2021-002"),
    ]:
        changed = Certificate(**{**base.to_dict(), name: new})
        assert canonicalize(changed) != base_bytes


def test_extra_and_missing_fields_rejected_in_mapping():
    d = make().to_dict()
    with pytest.raises(CertificateValidationError):
        canonicalize({**d, "signature": "abc"})
    d.pop("degree")
    with pytest.raises(CertificateValidationError):
        canonicalize(d)


def test_canonicalize_rejects_other_types():
    with pytest.raises(CanonicalizationError):
        canonicalize("not a certificate")  # type: ignore[arg-type]


# ---- M3 compatibility --------------------------------------------------

def test_canonical_bytes_work_with_m3_primitives():
    key = Ed25519PrivateKey.generate()
    data = canonicalize(make())
    sig = sign_bytes(key, data)
    assert verify_bytes(key.public_key(), data, sig)
    tampered = canonicalize(make(student_name="Tampered"))
    assert not verify_bytes(key.public_key(), tampered, sig)