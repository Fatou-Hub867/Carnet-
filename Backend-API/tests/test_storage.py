"""Pure-logic helpers in core.storage: recovering the original filename from
a storage key, and building a safe Content-Disposition header value."""

import uuid

from core.storage import _content_disposition, original_filename_from_key


def test_original_filename_from_key_survives_hyphens_in_filename():
    key = f"{uuid.uuid4()}-rapport-radio-thorax-2024.pdf"
    assert original_filename_from_key(key) == "rapport-radio-thorax-2024.pdf"


def test_original_filename_from_key_plain_name():
    u = uuid.uuid4()
    key = f"{u}-diploma.pdf"
    assert original_filename_from_key(key) == "diploma.pdf"


def test_content_disposition_includes_ascii_fallback_and_utf8_variant():
    header = _content_disposition("ordonnance été.pdf")
    assert header.startswith("attachment; filename=")
    assert 'filename="ordonnance t.pdf"' in header  # accents dropped, not mangled
    assert "filename*=UTF-8''ordonnance%20%C3%A9t%C3%A9.pdf" in header


def test_content_disposition_strips_header_injection_attempts():
    header = _content_disposition('evil"\r\nX-Injected: yes')
    assert "\r" not in header
    assert "\n" not in header
    assert (
        header
        == "attachment; filename=\"evilX-Injected: yes\"; filename*=UTF-8''evilX-Injected%3A%20yes"
    )
