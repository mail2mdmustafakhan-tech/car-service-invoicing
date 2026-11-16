"""Tests for the business logo.

The logo is uploaded by whoever runs the shop, so the interesting cases are
the ones where the upload is not what it claims to be.
"""

from __future__ import annotations

import pytest

from app import repository as repo

# The smallest valid files of each kind, enough to exercise the sniffing
# without carrying real images around in the test suite.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 24


# --------------------------------------------------------------------------
# What counts as an image
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "data, expected",
    [(PNG, "image/png"), (JPEG, "image/jpeg"), (GIF, "image/gif"), (WEBP, "image/webp")],
)
def test_recognises_real_images(data, expected):
    assert repo.sniff_image(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"hello world",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"%PDF-1.4",
        b"RIFF\x24\x00\x00\x00WAVE",          # a sound file, not a picture
        b"\x89PNG",                            # a truncated signature
    ],
)
def test_rejects_everything_else(data):
    assert repo.sniff_image(data) is None


def test_the_declared_type_is_not_trusted(conn):
    """A browser's content-type is supplied by the uploader; the bytes are not.

    Someone renaming a script to .png must not get it served back from the
    application's own address.
    """
    with pytest.raises(ValueError, match="not a PNG"):
        repo.set_logo(conn, b"<svg onload='steal()'></svg>", filename="logo.png")


# --------------------------------------------------------------------------
# Storing it
# --------------------------------------------------------------------------

def test_no_logo_to_begin_with(conn):
    assert repo.get_logo(conn) is None
    assert repo.logo_data_uri(conn) == ""
    assert repo.logo_state(conn)["logo_mime"] == ""


def test_round_trip(conn):
    assert repo.set_logo(conn, PNG, filename="arc-logo.png") == "image/png"
    data, mime = repo.get_logo(conn)
    assert data == PNG                      # byte for byte, not re-encoded
    assert mime == "image/png"
    assert repo.logo_state(conn)["logo_filename"] == "arc-logo.png"


def test_an_empty_upload_is_refused(conn):
    with pytest.raises(ValueError, match="No file"):
        repo.set_logo(conn, b"")


def test_an_oversized_image_is_refused(conn):
    too_big = PNG + b"\x00" * repo.MAX_LOGO_BYTES
    with pytest.raises(ValueError, match="under 1 MB"):
        repo.set_logo(conn, too_big)


def test_replacing_and_removing(conn):
    repo.set_logo(conn, PNG)
    repo.set_logo(conn, GIF)
    assert repo.get_logo(conn)[1] == "image/gif"

    repo.clear_logo(conn)
    assert repo.get_logo(conn) is None
    assert repo.logo_state(conn)["logo_filename"] == ""


def test_data_uri_is_embeddable(conn):
    repo.set_logo(conn, PNG)
    uri = repo.logo_data_uri(conn)
    assert uri.startswith("data:image/png;base64,")

    from base64 import b64decode
    assert b64decode(uri.split(",", 1)[1]) == PNG


def test_the_logo_travels_with_a_backup(conn, tmp_path):
    """It lives in the database precisely so the backup button catches it."""
    import sqlite3

    from app.db import backup_to

    repo.set_logo(conn, PNG, filename="arc-logo.png")
    source = conn.execute("PRAGMA database_list").fetchone()["file"]
    target = backup_to(tmp_path / "backup.db", source)

    copy = sqlite3.connect(target)
    copy.row_factory = sqlite3.Row
    row = copy.execute("SELECT logo_blob, logo_mime FROM branding").fetchone()
    assert bytes(row["logo_blob"]) == PNG
    assert row["logo_mime"] == "image/png"
    copy.close()


# --------------------------------------------------------------------------
# Through the web
# --------------------------------------------------------------------------

def test_no_logo_serves_a_404(client):
    assert client.get("/logo").status_code == 404


def test_uploading_through_settings(client):
    response = client.post(
        "/settings/logo",
        files={"logo": ("arc-logo.png", PNG, "image/png")},
        follow_redirects=True,
    )
    assert response.status_code == 200

    served = client.get("/logo")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/png")
    assert served.content == PNG
    # Browsers must not be allowed to second-guess the type of a file someone
    # else uploaded.
    assert served.headers["x-content-type-options"] == "nosniff"


def test_a_bad_upload_is_reported_not_crashed(client):
    response = client.post(
        "/settings/logo",
        files={"logo": ("notreally.png", b"just some text", "image/png")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "not a PNG" in response.text
    assert client.get("/logo").status_code == 404


def test_removing_through_settings(client):
    client.post("/settings/logo", files={"logo": ("l.png", PNG, "image/png")})
    assert client.get("/logo").status_code == 200

    client.post("/settings/logo/remove", follow_redirects=True)
    assert client.get("/logo").status_code == 404


def test_the_logo_appears_in_the_top_bar(client):
    assert "/logo?v=" not in client.get("/").text
    client.post("/settings/logo", files={"logo": ("l.png", PNG, "image/png")})
    assert "/logo?v=" in client.get("/").text


def test_the_logo_url_carries_a_version(client):
    """Without it, a replaced logo keeps showing from the browser's cache."""
    import re

    client.post("/settings/logo", files={"logo": ("l.png", PNG, "image/png")})
    url = re.search(r'/logo\?v=[^"]+', client.get("/").text).group(0)

    assert url.startswith("/logo?v=")
    assert len(url) > len("/logo?v=")      # a timestamp, not an empty value


def test_the_printed_documents_embed_the_logo(shop):
    """Linking to it would leave the PDF renderer with nothing to fetch."""
    shop.post("/settings/logo", files={"logo": ("l.png", PNG, "image/png")})
    shop.post(
        "/invoices/new",
        data={"customer_id": "1", "issue_date": "2026-11-11", "vat_rate": "15",
              "status": "issued", "item_description": ["Service"], "item_qty": ["1"],
              "item_price": ["100"], "item_kind": ["service"], "item_unit": ["pcs"],
              "item_catalog_id": [""], "item_description_ar": [""]},
    )
    page = shop.get("/invoices/1/print?autoprint=0").text
    assert "data:image/png;base64," in page
    assert 'src="/logo' not in page


def test_documents_print_fine_without_a_logo(shop):
    shop.post(
        "/invoices/new",
        data={"customer_id": "1", "issue_date": "2026-11-11", "vat_rate": "15",
              "status": "issued", "item_description": ["Service"], "item_qty": ["1"],
              "item_price": ["100"], "item_kind": ["service"], "item_unit": ["pcs"],
              "item_catalog_id": [""], "item_description_ar": [""]},
    )
    page = shop.get("/invoices/1/print?autoprint=0").text
    assert "doc-logo" not in page
    assert "TAX INVOICE" in page
