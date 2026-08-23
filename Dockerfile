FROM python:3-slim AS wheel_builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY backend ./backend

RUN cd backend && uv build && mkdir /out/ && cp dist/*.whl /out/

# Final image
FROM python:3-slim

ENV PYTHONUNBUFFERED=1
# yt-dlp shells out to Deno to solve YouTube's JS challenges (see backend/pyproject.toml). Deno itself is installed
# as a Python dependency (the "deno" extra), but it still needs a writable cache directory: by default it uses
# $HOME/.cache/deno, and the "python" user below is a homeless system account, so point it somewhere writable and
# quiet its automatic update check.
ENV DENO_DIR=/var/cache/deno
ENV DENO_NO_UPDATE_CHECK=1

RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg nginx && apt-get clean && rm -rf /var/lib/apt/lists/* && \
  useradd -r python && usermod -g www-data python && mkdir /data && chown python:www-data /data && \
  mkdir -p "$DENO_DIR" && chown python:www-data "$DENO_DIR"

COPY --from=wheel_builder /out/*.whl /tmp/
RUN pip3 install --no-cache-dir /tmp/*.whl supervisor && rm /tmp/*.whl

COPY frontend/src /var/www/html
COPY default_site /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/supervisord.conf

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
