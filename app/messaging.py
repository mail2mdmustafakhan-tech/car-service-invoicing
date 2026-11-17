"""Sending an estimate to a customer by WhatsApp or SMS.

Nothing here talks to a network. It builds the links a browser or phone can
open -- ``https://wa.me/...`` and ``sms:...`` -- with the message already
written. The user presses send.

That is a deliberate starting point rather than a limitation worth hiding:
it works today, costs nothing, needs no Meta Business account, no template
approval and no API key, and it sends from the shop's own WhatsApp number so
replies land where someone will see them. What it cannot do is attach the
PDF or send unattended. :func:`provider_note` says so in the interface rather
than letting anyone discover it mid-job.

To add a real provider later, write a function that takes the same
``(phone, message)`` that :func:`whatsapp_link` takes and posts it to an API.
The rest of the application does not need to change.
"""

from __future__ import annotations

from urllib.parse import quote

#: Arabic-Indic and Eastern Arabic-Indic digits mapped onto ASCII, so a number
#: typed on an Arabic keyboard dials the same as one typed on a Latin one.
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalise_phone(raw: str | None, country_code: str = "966") -> str:
    """Turn however a number was typed into the international form, digits only.

    WhatsApp needs a full international number with no plus sign, spaces or
    dashes. Phone numbers in a customer list are written every possible way,
    so this takes the common ones rather than demanding one format.

    >>> normalise_phone("0551234567")
    '966551234567'
    >>> normalise_phone("+966 55 123 4567")
    '966551234567'
    >>> normalise_phone("00966551234567")
    '966551234567'
    >>> normalise_phone("966551234567")
    '966551234567'
    >>> normalise_phone("055-123 4567")
    '966551234567'
    >>> normalise_phone("٠٥٥١٢٣٤٥٦٧")
    '966551234567'
    >>> normalise_phone("", "966")
    ''
    >>> normalise_phone("not a phone")
    ''

    A different country works the same way:

    >>> normalise_phone("07700 900123", country_code="44")
    '447700900123'
    """
    if not raw:
        return ""

    text = str(raw).translate(_ARABIC_DIGITS).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""

    code = "".join(ch for ch in str(country_code) if ch.isdigit()) or "966"

    # 00 is how much of the world writes the leading +.
    if digits.startswith("00"):
        digits = digits[2:]

    if digits.startswith(code):
        return digits
    if digits.startswith("0"):
        return code + digits.lstrip("0")

    # A bare local number with no trunk prefix.
    return code + digits


def whatsapp_link(phone: str, message: str = "", country_code: str = "966") -> str:
    """A click-to-chat link that opens WhatsApp with the message ready to send.

    Returns an empty string when there is no usable number, so the interface
    can leave the button out rather than offering one that goes nowhere.

    >>> whatsapp_link("0551234567", "Hello")
    'https://wa.me/966551234567?text=Hello'
    >>> whatsapp_link("")
    ''
    """
    number = normalise_phone(phone, country_code)
    if not number:
        return ""
    base = f"https://wa.me/{number}"
    return f"{base}?text={quote(message)}" if message else base


def sms_link(phone: str, message: str = "", country_code: str = "966") -> str:
    """An ``sms:`` link, which opens the messaging app on a phone or tablet.

    >>> sms_link("0551234567", "Hello")
    'sms:+966551234567?body=Hello'
    >>> sms_link("")
    ''
    """
    number = normalise_phone(phone, country_code)
    if not number:
        return ""
    base = f"sms:+{number}"
    return f"{base}?body={quote(message)}" if message else base


def render_template(template: str, values: dict[str, str]) -> str:
    """Fill ``{placeholder}`` markers in a message template.

    Deliberately not ``str.format``: the template is typed by the user in
    Settings, and a stray brace or an unknown name should leave the text
    alone rather than raise an error in the middle of sending a quote.

    >>> render_template("Hi {customer}, total {total}.",
    ...                 {"customer": "Ahmed", "total": "250.00 SAR"})
    'Hi Ahmed, total 250.00 SAR.'
    >>> render_template("Hi {customer}, ref {unknown}.", {"customer": "Ahmed"})
    'Hi Ahmed, ref {unknown}.'
    >>> render_template("100% { not a placeholder }", {})
    '100% { not a placeholder }'
    """
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def summarise_items(descriptions: list[str], limit: int = 6) -> str:
    """A short bulleted list of what is being quoted, for the message body.

    Superseded by :func:`itemise`, which carries the prices too. Kept because
    a customer's saved message template may still name it indirectly through
    a stored ``{items}`` placeholder built before the change, and because
    dropping a working function to replace it with a better one is how a
    quiet regression gets shipped.

    >>> summarise_items(["Oil change", "Brake pads"])
    '- Oil change\\n- Brake pads'
    >>> summarise_items([f"Item {n}" for n in range(1, 9)], limit=3)
    '- Item 1\\n- Item 2\\n- Item 3\\n- ...and 5 more'
    >>> summarise_items([])
    ''
    """
    if not descriptions:
        return ""
    shown = [f"- {text}" for text in descriptions[:limit]]
    remaining = len(descriptions) - limit
    if remaining > 0:
        shown.append(f"- ...and {remaining} more")
    return "\n".join(shown)


def itemise(lines: list[dict[str, str]], limit: int = 12, more: str = "and {n} more") -> str:
    """The priced breakdown that goes in the message body.

    A total on its own invites the reply "what for?", and that reply arrives
    by phone, to somebody holding a spanner. Listing the work with its price
    answers it before it is asked.

    Each line is a dict of already-formatted strings -- ``description``,
    ``qty``, ``price`` and ``amount`` -- because the money and quantity
    formatting rules live in :mod:`app.money` and must not be reinvented
    here with a different idea of how many decimal places a riyal has.

    A quantity of one is left out. "Oil change: 200.00" is how someone would
    say it; "Oil change: 1 x 200.00 = 200.00" is how a spreadsheet would.

    >>> print(itemise([{"description": "Oil change", "qty": "1",
    ...                 "price": "200.00", "amount": "200.00"}]))
    - Oil change: 200.00

    >>> print(itemise([{"description": "Brake pads", "qty": "2",
    ...                 "price": "150.00", "amount": "300.00"}]))
    - Brake pads: 2 × 150.00 = 300.00

    Long lists are cut short, because a message listing forty parts is not
    read and the printed estimate is what carries the full detail:

    >>> lines = [{"description": f"Part {n}", "qty": "1",
    ...           "price": "10.00", "amount": "10.00"} for n in range(1, 6)]
    >>> print(itemise(lines, limit=2))
    - Part 1: 10.00
    - Part 2: 10.00
    - ...and 3 more

    >>> itemise([])
    ''
    """
    if not lines:
        return ""

    out = []
    for line in lines[:limit]:
        description = (line.get("description") or "").strip()
        qty = (line.get("qty") or "").strip()
        price = (line.get("price") or "").strip()
        amount = (line.get("amount") or "").strip()

        if qty and qty not in ("1", "1.0", "١"):
            out.append(f"- {description}: {qty} × {price} = {amount}")
        else:
            out.append(f"- {description}: {amount}")

    remaining = len(lines) - limit
    if remaining > 0:
        out.append("- ..." + more.replace("{n}", str(remaining)))
    return "\n".join(out)


def provider_note(lang: str = "en") -> str:
    """One line saying what this way of sending can and cannot do."""
    if lang == "ar":
        return (
            "يفتح واتساب مع الرسالة جاهزة — اضغط إرسال. "
            "لإرفاق ملف PDF، أرفقه يدوياً بعد فتح المحادثة."
        )
    return (
        "Opens WhatsApp with the message ready — you press send. "
        "To include the PDF, attach it yourself once the chat opens."
    )
