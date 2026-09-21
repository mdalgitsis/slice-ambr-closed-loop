FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir requests

COPY grafana/dashboard_manager.py /app/
COPY grafana/dashboard.json /app/

USER 1000

ENTRYPOINT ["python", "-u", "dashboard_manager.py"]
