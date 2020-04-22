FROM python:3-buster as wheel_builder

COPY backend ./backend
RUN pip3 install poetry
RUN cd backend && poetry build && mkdir /out/ && cp dist/*.whl /out/

FROM python:3-buster

ENV PYTHONUNBUFFERED=1

COPY --from=wheel_builder /out/*.whl /tmp/
RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg nginx && apt-get clean && rm -rf /var/lib/apt/lists/* && \
  pip3 install --no-cache-dir /tmp/*.whl supervisor && rm /tmp/*.whl && \
  useradd -r python && usermod -g www-data python && mkdir /data && chown python:www-data /data

COPY frontend/ /var/www/html
COPY default_site /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/supervisord.conf

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

