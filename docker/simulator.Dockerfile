FROM python:3.12-slim

# Non-root by default; the chart also enforces this, but an image that only
# works when the chart is right is an image that will eventually run as root.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ /app/agents/
COPY simulator/ /app/simulator/

USER 1000
EXPOSE 8999

CMD ["python", "-u", "-m", "simulator.closed_loop"]
