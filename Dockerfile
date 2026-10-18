FROM python:3.14.8-slim-trixie

ARG BUILD_VERSION=dev
ARG VCS_REF=unknown
ARG SOURCE_URL=https://github.com/paulcakeface/vhscribe

LABEL org.opencontainers.image.title="VHScribe" \
      org.opencontainers.image.description="Local-first VHS capture control panel" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VHSCRIBE_VERSION=${BUILD_VERSION} \
    VHSCRIBE_VCS_REF=${VCS_REF}

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        alsa-utils \
        ffmpeg \
        tini \
        v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN mkdir -p /app/logs /app/state /captures

EXPOSE 8090
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "1", "--proxy-headers"]
