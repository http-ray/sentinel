# Runs the FastAPI server. sentence-transformers/torch (the optional
# `embeddings` extra) is deliberately NOT installed here -- keeps the image
# small and the default build fast, consistent with SENTINEL_USE_EMBEDDINGS
# defaulting to false everywhere else in this project.
FROM python:3.12-slim

WORKDIR /app

# Copy dependency metadata first so dependency install is cached separately
# from application code changes.
COPY pyproject.toml README.md ./
COPY sentinel ./sentinel
COPY scripts ./scripts
COPY runbooks ./runbooks
COPY fixtures ./fixtures

# Editable install, deliberately: sentinel/config.py resolves runbooks_dir/
# fixtures_dir/db_path relative to the sentinel package's own __file__, which
# only points back at /app (this directory) if the install stays editable --
# a normal `pip install .` would copy the package into site-packages and
# silently break those defaults. See docs/engineering-log.md.
RUN pip install --no-cache-dir -e .

RUN useradd --create-home --uid 1000 sentinel \
    && mkdir -p /app/data \
    && chown -R sentinel:sentinel /app
USER sentinel

# Default SQLite location inside the image; compose overrides this to point
# at a named volume so incidents survive container recreation.
ENV SENTINEL_DB_PATH=/app/data/sentinel.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "sentinel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
