FROM python:3-slim

WORKDIR /app/

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

ENTRYPOINT ["python", "/app/smart-ipv6-rotator.py"]
