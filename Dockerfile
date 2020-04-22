FROM python:3-buster as wheel_builder

RUN pip3 install poetry

COPY backend ./backend

RUN cd backend && poetry build && mkdir /out/ && cp dist/*.whl /out/

# Final image
FROM python:3-buster

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg nginx && apt-get clean && rm -rf /var/lib/apt/lists/* && \
  useradd -r python && usermod -g www-data python && mkdir /data && chown python:www-data /data

COPY --from=wheel_builder /out/*.whl /tmp/
RUN pip3 install --no-cache-dir /tmp/*.whl supervisor && rm /tmp/*.whl

COPY frontend/ /var/www/html
COPY default_site /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/supervisord.conf

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
