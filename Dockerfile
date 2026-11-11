# Car Service Invoicing -- container image
#
# Build:  docker build -t car-service-invoicing .
# Run:    docker compose up -d
#
# The image includes WeasyPrint and its system libraries, so the "Download
# PDF" button works out of the box here even though it is optional elsewhere.

FROM python:3.12-slim

# Pango and Cairo are what WeasyPrint uses to lay out and shape text. They
# are also what makes Arabic render correctly in the PDF, so they earn the few
# megabytes. fonts-noto-core supplies an Arabic face; without it the PDF falls
# back to a font with no Arabic glyphs and the text comes out as empty boxes.
#
# libharfbuzz-subset0 is installed separately and tolerantly: WeasyPrint only
# warns when it is absent, and the package name has moved between Debian
# releases. A rename should not break the whole build over a warning.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        fonts-dejavu-core \
        fonts-noto-core \
        curl \
 && (apt-get install --no-install-recommends -y libharfbuzz-subset0 \
     || echo "libharfbuzz-subset0 not available; continuing without it") \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CARSERVICE_DB=/data/carservice.db \
    CARSERVICE_HOST=0.0.0.0 \
    CARSERVICE_PORT=8000

WORKDIR /srv

# Dependencies are copied and installed before the application code, so that
# editing a template does not force a reinstall on the next build.
COPY requirements.txt ./
RUN pip install -r requirements.txt && pip install "weasyprint>=60"

COPY app ./app

RUN mkdir -p /data

# The database lives on a mounted volume, so it survives the container being
# rebuilt, upgraded or thrown away. docker-compose.yml maps this to the ./data
# folder next to it, where you can see and copy the file.
#
# Note on the user: this container runs as root. The usual advice is to add an
# unprivileged user, and for an image on the public internet that is right.
# Here it would work against you. ./data is a folder on the host; a non-root
# user inside the container would have a different numeric id from the one
# that owns that folder, and the application would fail to write the database
# on its first start with a permissions error that is unpleasant to diagnose.
# This is a single-tenant application on an office network with no login of
# its own, so the gain would have been small and the breakage real. To harden
# it later, switch docker-compose.yml to a named volume and add a USER line.
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
