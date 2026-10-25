FROM python:3.12-slim AS builder
WORKDIR /build
COPY . .
RUN python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JEV_DB=/data/jev.sqlite
WORKDIR /app
COPY requirements.lock /app/requirements.lock
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir -r requirements.lock /wheels/*.whl \
    && useradd --uid 10001 --create-home app \
    && mkdir /data && chown app:app /data \
    && rm -rf /wheels
COPY scripts /app/scripts
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"
CMD ["uvicorn", "jev_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
