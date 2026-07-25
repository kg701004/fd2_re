# Reproducible FD2 remake test image.  Ebiten's Linux backend needs the ALSA
# pkg-config metadata even when tests do not open an audio device.
FROM golang:1.22-bookworm

ENV PATH=/usr/local/go/bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/remake
