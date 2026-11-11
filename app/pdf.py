"""Optional server-side PDF generation.

There are two ways to get a PDF out of this application, and both are
supported on purpose:

1. **The browser's print dialogue.** Open an invoice's print view and choose
   "Save as PDF". This needs no extra software, works on every operating
   system, and renders Arabic correctly because the browser does the text
   shaping. For a single office machine this is usually all that is needed.

2. **A real download link**, using WeasyPrint. Nicer when invoices are emailed
   rather than handed over, but WeasyPrint needs system libraries
   (Pango and Cairo) that are fiddly to install on Windows.

So WeasyPrint is an *optional* dependency. It is pre-installed in the Docker
image, where those libraries come along for free. If it is missing, the PDF
button simply sends the user to the print view instead -- the application does
not fail to start, and nothing has to be configured.

To add it to a non-Docker install::

    pip install weasyprint
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

try:  # pragma: no cover - depends on what is installed
    from weasyprint import CSS, HTML  # type: ignore[import-untyped]

    PDF_AVAILABLE = True
except Exception:  # ImportError, or missing system libraries at import time
    HTML = None  # type: ignore[assignment]
    CSS = None  # type: ignore[assignment]
    PDF_AVAILABLE = False


class PdfNotAvailable(RuntimeError):
    """Raised if a PDF is requested without WeasyPrint installed."""


def html_to_pdf(
    html: str,
    *,
    base_url: str | None = None,
    stylesheets: Sequence[Path | str] = (),
) -> bytes:
    """Render a finished HTML page to PDF bytes.

    ``stylesheets`` are passed as real files rather than left to the ``<link>``
    in the page. A browser resolves ``/static/css/print.css`` against the
    running server, but WeasyPrint is handed a string of HTML with no server
    behind it, so that same path would be looked for at the root of the disk
    and silently not found -- producing an unstyled PDF. Handing it the file
    directly removes the guesswork.

    ``base_url`` is still used to resolve anything else the page references,
    such as an image.
    """
    if not PDF_AVAILABLE or HTML is None or CSS is None:
        raise PdfNotAvailable(
            "PDF download needs WeasyPrint. Install it with 'pip install weasyprint', "
            "or use the Print button and choose 'Save as PDF' in the browser."
        )
    sheets = [CSS(filename=str(path)) for path in stylesheets]
    return HTML(string=html, base_url=base_url).write_pdf(stylesheets=sheets)
