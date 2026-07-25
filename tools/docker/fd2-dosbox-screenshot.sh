#!/usr/bin/env bash
# Run the user-owned FD2 DOS build inside Xvfb and execute a small input/
# screenshot timeline. /game is a disposable writable sandbox; /shots is an
# explicit output mount. The original game directory is never mounted here.
set -euo pipefail

timeline="${1:-wait:12;shot:title}"
cycles="${2:-fixed 12000}"
export DISPLAY=:99

mkdir -p /shots /shots/dosbox-captures
Xvfb :99 -screen 0 1024x768x24 -nolisten tcp &
xvfb_pid=$!

cleanup() {
    kill "${dosbox_pid:-}" 2>/dev/null || true
    kill "$xvfb_pid" 2>/dev/null || true
}
trap cleanup EXIT

cat >/tmp/fd2-dosbox.conf <<EOF
[sdl]
fullscreen=false
fulldouble=false
output=surface
autolock=false
waitonerror=false

[dosbox]
machine=svga_s3
captures=/shots/dosbox-captures
memsize=32

[render]
frameskip=0
aspect=false
scaler=none

[cpu]
core=auto
cputype=auto
cycles=${cycles}

[mixer]
nosound=true
[midi]
mpu401=none
[sblaster]
sbtype=none
[gus]
gus=false
[speaker]
pcspeaker=false
[joystick]
joysticktype=none
[dos]
xms=true
ems=true
umb=true
keyboardlayout=us

[autoexec]
mount c /game
c:
FD2.EXE
EOF

dosbox -conf /tmp/fd2-dosbox.conf > /tmp/fd2-dosbox.log 2>&1 &
dosbox_pid=$!

window=""
for _ in $(seq 1 30); do
    window=$(xdotool search --name DOSBox 2>/dev/null | head -1 || true)
    [[ -n "$window" ]] && break
    sleep 0.5
done
if [[ -z "$window" ]]; then
    cat /tmp/fd2-dosbox.log >&2
    exit 1
fi

xdotool windowfocus "$window"
IFS=';' read -ra steps <<< "$timeline"
for step in "${steps[@]}"; do
    [[ -z "$step" ]] && continue
    kind="${step%%:*}"
    arg="${step#*:}"
    case "$kind" in
        wait) sleep "$arg" ;;
        key) xdotool windowfocus "$window"; xdotool key "$arg" ;;
        type) xdotool windowfocus "$window"; xdotool type --delay 80 "$arg" ;;
        shot) import -window root "/shots/${arg}.png" ;;
        *) echo "unknown timeline step: $step" >&2; exit 2 ;;
    esac
done
