# Car Service Invoicing -- container image
#
# Build:  docker build -t car-service-invoicing .
# Run:    docker compose up -d
#
# The image includes WeasyPrint and its system libraries, so the "Download
# PDF" button works out of the box here even though it is optional elsewhere.

FROM python:3.12-slim

# Pango and Cairo are what WeasyPrint uses to lay out and shape text. They
# are also what makes Arabic render correctly in the PDF, so they are worth
# the few megabytes.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fonts-dejavu-core \
        fonts-noto-core \
        curl \
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

# The database lives on a mounted volume, so it survives the container being
# rebuilt, upgraded or thrown away.
VOLUME ["/data"]
EXPOSE 8000

# Run as a non-root user; it still owns /data so it can write the database.
RUN useradd --create-home --uid 10001 carservice \
 && mkdir -p /data \
 && chown -R carservice:carservice /data /srv
USER carservice

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
