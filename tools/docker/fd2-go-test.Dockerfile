# Reproducible FD2 remake test image. Ebiten's Linux backend compiles GLFW
# and Oto even when tests do not open a window or audio device.
FROM golang:1.22-bookworm

ENV PATH=/usr/local/go/bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        pkg-config libasound2-dev xorg-dev libgl1-mesa-dev xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/remake

# Keep the test invocation hermetic after image build: dependencies are fetched
# while building this explicit development image, never from the host or during
# the verification command.
COPY remake/go.mod remake/go.sum ./
RUN go mod download
