FROM python:3-slim

WORKDIR /app/

COPY . .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ./


ENTRYPOINT ["python", "/app/smart-ipv6-rotator.py"]
