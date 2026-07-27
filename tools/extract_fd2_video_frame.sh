#!/usr/bin/env bash
# Extract the centered DOS 320x200 image from the checked-in ch01 recording.
# The recording is 1440x1080 with a 1408x880 (4.4x) game viewport at (16,100).
# Because the source has already been resampled, this is an E2 layout oracle,
# not a palette-index or byte-exact framebuffer oracle.
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 VIDEO TIMESTAMP OUTPUT.png" >&2
    exit 2
fi

video=$1
timestamp=$2
output=$3
crop=${FD2_VIDEO_CROP:-1408:880:16:100}

ffmpeg -hide_banner -loglevel error -y \
    -ss "$timestamp" -i "$video" -frames:v 1 \
    -vf "crop=${crop},scale=320:200:flags=lanczos" \
    "$output"
