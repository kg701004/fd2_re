#!/usr/bin/env bash
#
# 2026-09-03 全工具驗證:待淘汰(deprecated),但保留。比對對象 remake 已於
# 2026-09-02 移除,「DOSBox-X vs remake」這個主要用途沒有對象了;原版側的
# raw 320x200 擷取與 pulse 相位鎖定仍可用。新工作請改用
# tools/fd2_original_verify.py + tools/dosbox_harness.sh。
# Byte-exact DOSBox-X raw-framebuffer capture harness, WSL side.
#
# Backs the UI-VIS-DIFF-HARNESS tool (docs/knowledge-base/91-worklist.md):
# "固定同一FD2.SAV／roster／camera／cursor／tick，輸出DOSBox與remake 320×200
# pair及pixel diff". This script is the DOSBox-X half; tools/dosbox_diff_harness.py
# (Windows side) drives it, drives the remake capture, and produces the diff.
#
# WHY A SEPARATE SCRIPT FROM tools/dosbox_harness.sh
# ---------------------------------------------------
# dosbox_harness.sh's `screenshot` subcommand does `import -window root` on
# whatever size the DOSBox-X SDL window happens to be -- fine for windowed
# visual inspection, but NOT byte-exact: the window is normally larger than
# the game's native 320x200 mode, so getting down to 320x200 needs a resize
# (see docs/knowledge-base/91-worklist.md's UI-VIS-TOWN entry: variant1/2
# used exactly this "import -window root, then crop/resize" method and
# explicitly fell short of "byte-exact RGB MD5" rigor as a result).
#
# This script instead launches dosbox-x with an SDL/render config that pins
# the window to the emulated video mode's *native* resolution with no
# scaler and no aspect correction:
#   [sdl]    output=surface
#   [render] scaler=none / aspect=false
# These are the exact three settings tools/docker/fd2-dosbox-screenshot.sh
# used under the (now-removed, see memory project_docker_desktop_af_unix_broken)
# Docker pipeline that produced the UI-08-TOWN-VARIANT0-SIX-SELECTION-E2
# byte-exact raw RGB MD5 evidence. With them, the captured window's pixel
# buffer IS the raw 320x200 framebuffer -- no crop/resize math, no
# resampling, nothing that could quietly change a pixel value.
#
# Everything else (isolation model, Xvfb TCP display, private tmux server,
# per-instance workdir, the "launch must stay backgrounded with a trailing
# `exec sleep`" requirement) is copied from tools/dosbox_harness.sh --
# see docs/knowledge-base/98-tooling-infrastructure.md for the full
# rationale. Kept as an independent script (own registry dir, own tmux
# socket, own Xvfb port range) specifically so a parallel agent using the
# shared dosbox_harness.sh is never affected by anything here, and vice
# versa.
#
# Usage:
#   dosbox_diff_harness.sh launch <name> [keepalive_seconds] [sav_file]
#   dosbox_diff_harness.sh raw-screenshot <name> [output_path]
#   dosbox_diff_harness.sh send-keys <name> <key> [key2 ...]
#   dosbox_diff_harness.sh wait-pixel <name> <x,y,r,g,b> <delay_s> <max_tries>
#   dosbox_diff_harness.sh geometry <name>
#   dosbox_diff_harness.sh status
#   dosbox_diff_harness.sh teardown <name>
#   dosbox_diff_harness.sh teardown-all
#
# `launch` ends in a long `sleep` and must be invoked as a single
# backgrounded call (same WSLg-connection-reaping gotcha as dosbox_harness.sh
# -- do not wrap it in your own `&`, do not expect it to return promptly).
# All other subcommands are quick one-shot calls.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REGISTRY_DIR="${FD2_DIFFHARNESS_REGISTRY_DIR:-$HOME/.fd2-diffharness/instances}"
TMUX_SOCKET="${FD2_DIFFHARNESS_TMUX_SOCKET:-fd2diffharness}"
SOURCE_GAME_DIR="${FD2_DIFFHARNESS_SOURCE_DIR:-$HOME/fd2-run}"
# Deliberately plain `dosbox` (apt package, 0.74-3), NOT the dosbox-x heavy-
# debug build tools/dosbox_harness.sh uses. dosbox-x's windowed SDL output
# always draws an in-window GUI menu bar ("Main CPU Video Sound DOS Drive
# Capture Debug Help", confirmed live 2026-08-26) on top of the game surface
# even with output=surface/scaler=none/aspect=false, which adds chrome and
# makes the window strictly bigger than the native video mode -- exactly the
# byte-exactness problem this tool exists to avoid. Plain dosbox has no such
# chrome, so the same [sdl] output=surface + [render] scaler=none/aspect=false
# config (the one tools/docker/fd2-dosbox-screenshot.sh used, under the now-
# removed Docker pipeline, to get the UI-08-TOWN-VARIANT0 byte-exact
# evidence) makes its window exactly the emulated mode's native resolution
# with nothing else drawn into it. No debugger commands are needed for pure
# screen capture (per this tool's brief), so giving up dosbox-x's heavy-debug
# console here costs nothing.
DOSBOX_BIN="${FD2_DIFFHARNESS_DOSBOX_BIN:-$(command -v dosbox || echo /usr/bin/dosbox)}"
SCREENSHOT_DIR="${FD2_DIFFHARNESS_SHOT_DIR:-$REPO_ROOT/.wsl_build/diffharness}"
# Deliberately far from dosbox_harness.sh's :199/:299/... range and doc48
# §8.4 canonical :99, so the two tools can never collide even if both are
# mid-allocation at the same moment.
DISPLAY_BASE=799
DISPLAY_STEP=100
KEEPALIVE_DEFAULT=3600
RESERVED_NAMES=("dbg")

die() { echo "ERROR: $*" >&2; exit 1; }

validate_name() {
    local name=$1
    [[ "$name" =~ ^[a-zA-Z0-9_-]+$ ]] || die "instance name must match [a-zA-Z0-9_-]+, got: $name"
    for r in "${RESERVED_NAMES[@]}"; do
        [[ "$name" == "$r" ]] && die "instance name '$name' is reserved"
    done
}

state_file() { echo "$REGISTRY_DIR/$1.state"; }

load_state() {
    local name=$1
    local sf; sf=$(state_file "$name")
    [[ -f "$sf" ]] || die "no such instance: $name (no state file at $sf)"
    # shellcheck disable=SC1090
    source "$sf"
}

xvfb_alive() { local pid=$1; kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= 2>/dev/null | grep -q "Xvfb"; }
launcher_alive() { local pid=$1; kill -0 "$pid" 2>/dev/null; }
session_alive() { local session=$1; tmux -L "$TMUX_SOCKET" has-session -t "$session" 2>/dev/null; }

pick_display_port() {
    mkdir -p "$REGISTRY_DIR"
    local port=$DISPLAY_BASE
    while true; do
        local conflict=0
        local f
        for f in "$REGISTRY_DIR"/*.state; do
            [[ -e "$f" ]] || continue
            local p pid
            p=$(grep -oP '^DISPLAY_PORT=\K.*' "$f")
            pid=$(grep -oP '^XVFB_PID=\K.*' "$f")
            if [[ "$p" == "$port" ]] && xvfb_alive "$pid"; then
                conflict=1
                break
            fi
        done
        if ss -tln 2>/dev/null | grep -q ":$((6000 + port)) "; then
            conflict=1
        fi
        if [[ $conflict -eq 0 ]]; then
            echo "$port"
            return
        fi
        port=$((port + DISPLAY_STEP))
    done
}

# Writes the byte-exact dosbox-x config into $1/diffcapture.conf.
write_raw_capture_conf() {
    local workdir=$1
    cat >"$workdir/diffcapture.conf" <<EOF
[sdl]
fullscreen=false
fulldouble=false
output=surface
autolock=false
waitonerror=false

[dosbox]
machine=svga_s3
memsize=32

[render]
frameskip=0
aspect=false
scaler=none

[cpu]
core=normal
cputype=auto
cycles=5000

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
mount c $workdir
c:
FD2.EXE
EOF
}

cmd_launch() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: launch <name> [keepalive_seconds] [sav_file]"
    local keepalive=${2:-$KEEPALIVE_DEFAULT}
    local sav_override=${3:-}
    validate_name "$name"

    local sf; sf=$(state_file "$name")
    if [[ -f "$sf" ]]; then
        ( source "$sf"; xvfb_alive "$XVFB_PID" ) && die "instance '$name' already running (state file $sf); teardown first"
        rm -f "$sf"
    fi

    local port; port=$(pick_display_port)
    local session="diffharness-$name"
    local workdir="$HOME/fd2-run-diffharness-$name"

    [[ -d "$SOURCE_GAME_DIR" ]] || die "canonical game dir not found: $SOURCE_GAME_DIR"
    [[ -x "$DOSBOX_BIN" ]] || die "dosbox-x binary not found/executable: $DOSBOX_BIN"

    echo "[$name] preparing isolated workdir: $workdir"
    rm -rf "$workdir"
    mkdir -p "$workdir"
    cp -r "$SOURCE_GAME_DIR"/. "$workdir"/

    if [[ -n "$sav_override" ]]; then
        [[ -f "$sav_override" ]] || die "sav_file not found: $sav_override"
        echo "[$name] overriding FD2.SAV with $sav_override"
        cp "$sav_override" "$workdir/FD2.SAV"
    fi

    write_raw_capture_conf "$workdir"

    mkdir -p "$REGISTRY_DIR" "$SCREENSHOT_DIR"
    local xvfblog="$REGISTRY_DIR/$name.xvfb.log"

    echo "[$name] starting Xvfb on :$port (tcp-reachable as 127.0.0.1:$port)"
    # Screen must be at least as large as the biggest window the game ever
    # opens (the opening cutscene runs at a higher SVGA resolution than the
    # 320x200 gameplay mode this tool cares about, e.g. ~720x417 observed);
    # an undersized Xvfb screen clips/repositions the window and corrupts
    # the later native-resolution capture. 1024x768 matches dosbox_harness.sh.
    Xvfb ":$port" -screen 0 1024x768x24 -ac -nolisten local -listen tcp >"$xvfblog" 2>&1 &
    local xvfb_pid=$!
    sleep 3

    echo "[$name] starting dosbox-x (byte-exact raw-capture config) in tmux session '$session'"
    DISPLAY="127.0.0.1:$port" tmux -L "$TMUX_SOCKET" new-session -d -s "$session" -x 200 -y 50 \
        "cd '$workdir' && DISPLAY=127.0.0.1:$port '$DOSBOX_BIN' -conf '$workdir/diffcapture.conf'"
    sleep 2
    tmux -L "$TMUX_SOCKET" set-option -t "$session" remain-on-exit on

    cat >"$sf" <<EOF
NAME=$name
DISPLAY_PORT=$port
TMUX_SESSION=$session
WORKDIR=$workdir
XVFB_PID=$xvfb_pid
XVFB_LOG=$xvfblog
LAUNCHER_PID=$$
START_TIME=$(date +%s)
STATUS=starting
EOF

    echo "[$name] waiting for DOSBox window on display 127.0.0.1:$port ..."
    local winid="" i
    for i in $(seq 1 30); do
        winid=$(DISPLAY="127.0.0.1:$port" xdotool search --name DOSBox 2>/dev/null | head -1)
        [[ -n "$winid" ]] && break
        sleep 1
    done
    if [[ -z "$winid" ]]; then
        echo "[$name] WARNING: DOSBox window did not appear within 30s"
        sed -i 's/^STATUS=.*/STATUS=window_not_found/' "$sf"
    else
        local geom
        geom=$(DISPLAY="127.0.0.1:$port" xdotool getwindowgeometry --shell "$winid" 2>/dev/null)
        local w h
        w=$(echo "$geom" | grep -oP '^WIDTH=\K.*')
        h=$(echo "$geom" | grep -oP '^HEIGHT=\K.*')
        echo "[$name] window found ($winid), geometry ${w}x${h}"
        if [[ "$w" != "320" || "$h" != "200" ]]; then
            echo "[$name] WARNING: window is NOT the expected 320x200 native size -- raw-screenshot will refuse to claim byte-exact rigor until this resolves (see docs/knowledge-base/98-tooling-infrastructure.md)"
        fi
        echo "[$name] NOTE: boot/intro is not finished yet - screenshot-confirm the title screen yourself before send-keys."
        sed -i 's/^STATUS=.*/STATUS=running/' "$sf"
    fi

    echo "[$name] launch setup done, holding WSL connection alive for ${keepalive}s (do not kill this call)"
    exec sleep "$keepalive"
}

cmd_raw_screenshot() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: raw-screenshot <name> [output_path]"
    load_state "$name"
    local out=${2:-"$SCREENSHOT_DIR/${name}_$(date +%s).png"}
    mkdir -p "$(dirname "$out")"
    local win
    win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
    [[ -n "$win" ]] || die "no DOSBox window found for $name on 127.0.0.1:$DISPLAY_PORT"
    local geom w h
    geom=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool getwindowgeometry --shell "$win" 2>/dev/null)
    w=$(echo "$geom" | grep -oP '^WIDTH=\K.*')
    h=$(echo "$geom" | grep -oP '^HEIGHT=\K.*')
    if [[ "$w" != "320" || "$h" != "200" ]]; then
        die "refusing to claim a byte-exact capture: window is ${w}x${h}, not 320x200 (raw-capture config did not pin native resolution -- do not fall back to crop/resize, that is exactly the rigor gap this tool exists to close)"
    fi
    DISPLAY="127.0.0.1:$DISPLAY_PORT" import -window "$win" "$out" \
        || die "import screenshot failed for $name (display 127.0.0.1:$DISPLAY_PORT, window $win)"
    local rgbmd5
    rgbmd5=$(convert "$out" rgb:- | md5sum | cut -d' ' -f1)
    echo "$out rgb_md5=$rgbmd5"
}

cmd_geometry() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: geometry <name>"
    load_state "$name"
    local win
    win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
    [[ -n "$win" ]] || die "no DOSBox window found for $name on 127.0.0.1:$DISPLAY_PORT"
    DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool getwindowgeometry --shell "$win"
}

cmd_send_keys() {
    local name=${1:-}; shift || true
    [[ -n "$name" && $# -gt 0 ]] || die "usage: send-keys <name> <key> [key2 ...]"
    load_state "$name"
    local win
    win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
    [[ -n "$win" ]] || die "no DOSBox window found for $name on 127.0.0.1:$DISPLAY_PORT"
    local k nkeys=$#
    for k in "$@"; do
        DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool key --window "$win" "$k"
        sleep 0.1
    done
    echo "[$name] sent $nkeys key(s) to window $win"
}

cmd_wait_pixel() {
    local name=${1:-}; local spec=${2:-}; local delay=${3:-}; local max_tries=${4:-}
    [[ -n "$name" && -n "$spec" && -n "$delay" && -n "$max_tries" ]] || \
        die "usage: wait-pixel <name> <x,y,r,g,b> <delay_s> <max_tries>"
    load_state "$name"
    local x y red green blue
    IFS=',' read -r x y red green blue <<< "$spec"
    local expected="srgb(${red},${green},${blue})"
    local probe="$SCREENSHOT_DIR/${name}_pixel_probe.png"
    mkdir -p "$SCREENSHOT_DIR"
    local i actual=""
    for i in $(seq 1 "$max_tries"); do
        DISPLAY="127.0.0.1:$DISPLAY_PORT" import -window root "$probe" 2>/dev/null
        actual=$(convert "$probe" -format "%[pixel:p{$x,$y}]" info: 2>/dev/null)
        if [[ "$actual" == "$expected" ]]; then
            echo "[$name] wait-pixel matched after $i tries: ($x,$y)=$expected"
            return 0
        fi
        sleep "$delay"
    done
    die "wait-pixel timed out: expected ($x,$y)=$expected, last actual=$actual"
}

cmd_status() {
    mkdir -p "$REGISTRY_DIR"
    printf '%-12s %-10s %-8s %-16s %-8s %-8s %-10s %s\n' NAME DISPLAY XVFB_OK TMUX_SESSION SESS_OK LAUNCHER UPTIME_S WORKDIR
    local f any=0
    for f in "$REGISTRY_DIR"/*.state; do
        [[ -e "$f" ]] || continue
        any=1
        ( source "$f"
          xvfb_ok="no"; xvfb_alive "$XVFB_PID" && xvfb_ok="yes"
          sess_ok="no"; session_alive "$TMUX_SESSION" && sess_ok="yes"
          launch_ok="no"; launcher_alive "$LAUNCHER_PID" && launch_ok="yes"
          now=$(date +%s); uptime=$((now - START_TIME))
          printf '%-12s %-10s %-8s %-16s %-8s %-8s %-10s %s\n' \
              "$NAME" "127.0.0.1:$DISPLAY_PORT" "$xvfb_ok" "$TMUX_SESSION" "$sess_ok" "$launch_ok" "$uptime" "$WORKDIR"
        )
    done
    [[ $any -eq 1 ]] || echo "(no diffharness instances registered)"
}

cmd_teardown() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: teardown <name>"
    local sf; sf=$(state_file "$name")
    if [[ ! -f "$sf" ]]; then
        echo "[$name] no state file, nothing to do"
        return 0
    fi
    source "$sf"

    if session_alive "$TMUX_SESSION"; then
        echo "[$name] killing tmux session $TMUX_SESSION (socket $TMUX_SOCKET)"
        tmux -L "$TMUX_SOCKET" kill-session -t "$TMUX_SESSION"
    else
        echo "[$name] tmux session $TMUX_SESSION already gone"
    fi

    if kill -0 "$XVFB_PID" 2>/dev/null; then
        if ps -p "$XVFB_PID" -o args= 2>/dev/null | grep -q "Xvfb"; then
            echo "[$name] killing Xvfb pid $XVFB_PID"
            kill "$XVFB_PID" 2>/dev/null
            sleep 0.5
            kill -0 "$XVFB_PID" 2>/dev/null && kill -9 "$XVFB_PID" 2>/dev/null
        else
            echo "[$name] WARNING: pid $XVFB_PID no longer looks like Xvfb (reused?) - not killing"
        fi
    else
        echo "[$name] Xvfb pid $XVFB_PID already gone"
    fi

    if kill -0 "$LAUNCHER_PID" 2>/dev/null; then
        if ps -p "$LAUNCHER_PID" -o args= 2>/dev/null | grep -qE 'sleep|dosbox_diff_harness'; then
            echo "[$name] killing launcher/keepalive pid $LAUNCHER_PID"
            kill "$LAUNCHER_PID" 2>/dev/null
        else
            echo "[$name] WARNING: launcher pid $LAUNCHER_PID doesn't look like our keepalive (reused?) - not killing"
        fi
    fi

    rm -f "$sf"
    echo "[$name] torn down (workdir left in place: $WORKDIR - delete manually if not needed)"
}

cmd_teardown_all() {
    mkdir -p "$REGISTRY_DIR"
    local f name any=0
    for f in "$REGISTRY_DIR"/*.state; do
        [[ -e "$f" ]] || continue
        any=1
        name=$(basename "$f" .state)
        cmd_teardown "$name"
    done
    [[ $any -eq 1 ]] || echo "(no diffharness instances registered, nothing to tear down)"
}

main() {
    local cmd=${1:-}; shift || true
    case "$cmd" in
        launch)          cmd_launch "$@" ;;
        raw-screenshot)  cmd_raw_screenshot "$@" ;;
        geometry)        cmd_geometry "$@" ;;
        send-keys)       cmd_send_keys "$@" ;;
        wait-pixel)      cmd_wait_pixel "$@" ;;
        status)          cmd_status "$@" ;;
        teardown)        cmd_teardown "$@" ;;
        teardown-all)    cmd_teardown_all "$@" ;;
        *)
            cat >&2 <<EOF
usage: $0 <command> [args]
  launch <name> [keepalive_seconds] [sav_file]   start an isolated byte-exact-capture instance
  raw-screenshot <name> [output_path]            capture the native 320x200 window, no crop/resize
  geometry <name>                                print the DOSBox-X window's current geometry
  send-keys <name> <key> [key2 ...]              send game keypresses (xdotool key syntax)
  wait-pixel <name> <x,y,r,g,b> <delay_s> <tries> poll a root-window pixel until it matches
  status                                          list all diffharness-managed instances
  teardown <name>                                 kill one instance
  teardown-all                                    kill all diffharness instances
EOF
            exit 2
            ;;
    esac
}

main "$@"
