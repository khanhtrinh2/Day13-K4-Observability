from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_passport() -> None:
    out = scrub_text("My passport number is B1234567")
    assert "B1234567" not in out
    assert "REDACTED_PASSPORT_VN" in out


def test_scrub_address_with_street() -> None:
    out = scrub_text("Tôi ở 12 đường Nguyễn Huệ, quận 1")
    assert "REDACTED_ADDRESS_VN" in out


def test_scrub_address_admin_keyword() -> None:
    out = scrub_text("Địa chỉ: phường Bến Nghé, quận 1, TP.HCM")
    assert "REDACTED_ADDRESS_VN" in out
