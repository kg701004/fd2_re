#!/usr/bin/env bash
# Bash companion for tools/fd2_live_input_helper.py (M5 Phase 4 mechanical
# playtest primitives -- see that file's module docstring and
# docs/knowledge-base/98-tooling-infrastructure.md for the full writeup).
#
# WHY THIS IS A SEPARATE .sh FILE, NOT INLINE PYTHON-SIDE `wsl bash -c
# "multi; statement; script"` STRINGS (found the hard way building this tool,
# 2026-09-01): passing a multi-statement script as a single `bash -c
# "stmt1; stmt2"` (or embedded-newline) ARGUMENT through `wsl.exe` from the
# Windows side silently drops shell variable state between statements --
# `bash -c 'x=hello; echo got:$x'` invoked via Python's
# `subprocess.run(["wsl","-d","Ubuntu","bash","-c",cmd])` (a real argv list,
# NOT a shell string -- rules out Python/quoting-layer causes) prints
# `got:` (empty), even though `declare -p x` in the same `-c` string DOES
# show `x="hello"` correctly assigned. Piping the identical script via stdin
# to a bare `wsl -d Ubuntu bash` (no `-c`), or -- as done here -- writing it
# to a real `.sh` file and invoking `wsl -d Ubuntu bash /path/to/this.sh
# <args>`, both work perfectly, including real positional-argument passing
# ($1/$2/...). Root cause not fully diagnosed (likely something in how
# wsl.exe/interop re-tokenizes a `-c` argument containing `;`/newlines
# before bash ever sees it -- it is NOT bash itself: same script pasted into
# an interactive bash session works fine), but the workaround is exactly
# the pattern tools/dosbox_harness.sh and tools/dosbox_diff_harness.sh
# already used incidentally (a real script file, invoked with simple
# space-separated argv, never inline multi-statement -c strings depending
# on variable state) -- this section exists to make that CHOICE explicit and
# documented rather than accidental, since a future single-file rewrite of
# this tool as inline -c strings would silently reintroduce the bug.
#
# Usage:
#   fd2_live_input_helper.sh pick-port
#   fd2_live_input_helper.sh launch <name> <remake_dir> <campaign> <mute:0|1> <fdother|-> <fdtxt|-> <dato|-> [KEY=VAL ...]
#   fd2_live_input_helper.sh window-id <name>
#   fd2_live_input_helper.sh send-key <name> <xdotool-key-name>
#   fd2_live_input_helper.sh screenshot <name> <out_path> [resize_geometry] [autocrop:0|1] [view_out_path]
#     -- <out_path> is always the raw untouched capture; if resize/autocrop is
#        requested, the processed copy goes to <view_out_path> instead (never
#        overwrites <out_path>). Prints <out_path> on its own line, then
#        <view_out_path> on a second line if one was produced.
#   fd2_live_input_helper.sh wait-settle <name> <tmp_prefix> <max_tries> <interval_seconds>
#   fd2_live_input_helper.sh status
#   fd2_live_input_helper.sh teardown <name>
#   fd2_live_input_helper.sh teardown-all
#
# All subcommands are quick, one-shot, non-blocking calls (no long-lived
# foreground `sleep` keepalive like dosbox_harness.sh's `launch` needs --
# `nohup ... & disown` has been verified sufficient to keep both Xvfb and
# fd2-linux-verify alive across separate wsl.exe invocations, same technique
# dosbox_diff_harness.py's ensure_remake_xvfb() already relies on).

set -uo pipefail

REGISTRY_DIR="${FD2_LIVE_HELPER_REGISTRY_DIR:-$HOME/.fd2-live-helper/instances}"
DISPLAY_BASE=199
DISPLAY_STEP=100
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

xvfb_alive() { local pid=$1; [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= 2>/dev/null | grep -q "Xvfb"; }
game_alive() { local pid=$1; [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= 2>/dev/null | grep -q "fd2-linux-verify"; }

cmd_pick_port() {
    mkdir -p "$REGISTRY_DIR"
    local port=$DISPLAY_BASE
    while true; do
        local conflict=0 f
        for f in "$REGISTRY_DIR"/*.state; do
            [[ -e "$f" ]] || continue
            local p pid
            p=$(grep -oP '^DISPLAY_PORT=\K.*' "$f")
            pid=$(grep -oP '^XVFB_PID=\K.*' "$f")
            if [[ "$p" == "$port" ]] && xvfb_alive "$pid"; then conflict=1; break; fi
        done
        # Belt-and-suspenders (mirrors dosbox_harness.sh's pick_display_port):
        # also check nothing -- ours or any other tool's/instance's -- is
        # actually listening on the X TCP port already.
        if ss -tln 2>/dev/null | grep -q ":$((6000 + port)) "; then conflict=1; fi
        if [[ $conflict -eq 0 ]]; then echo "$port"; return; fi
        port=$((port + DISPLAY_STEP))
    done
}

# Fresh-every-time window id lookup (doc98's "remake 側 xdotool 合成鍵盤輸入
#可靠性" section: sending to a stale/wrong window id fails 100% silently,
# no error, no effect -- never cache this across calls). Greps xwininfo's
# tree for the GLFW window (Ebiten windows report WM_CLASS/name containing
# "GLFW"), prints its hex id, or exits nonzero with nothing on stdout.
find_window_id() {
    local port=$1
    DISPLAY="127.0.0.1:$port" xwininfo -root -tree 2>/dev/null \
        | grep -i "GLFW" | grep -oP '0x[0-9a-f]+' | head -1
}

cmd_window_id() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: window-id <name>"
    load_state "$name"
    xvfb_alive "$XVFB_PID" || die "instance '$name' Xvfb is not alive (pid $XVFB_PID)"
    local win; win=$(find_window_id "$DISPLAY_PORT")
    [[ -n "$win" ]] || die "no GLFW window found for '$name' on 127.0.0.1:$DISPLAY_PORT (game not up yet, or window title/class changed)"
    echo "$win"
}

cmd_launch() {
    local name=${1:-}; shift || true
    [[ -n "$name" ]] || die "usage: launch <name> <remake_dir> <campaign> <mute:0|1> <fdother|-> <fdtxt|-> <dato|-> [KEY=VAL ...]"
    validate_name "$name"
    local remake_dir=${1:-}; shift || true
    local campaign=${1:-assets/scenarios/campaign_full.json}; shift || true
    local mute=${1:-1}; shift || true
    # fdother/fdtxt/dato: "-" = omit (no native-asset env var set at all,
    # e.g. for scenes that need none); "" (empty/omitted) = default to the
    # canonical $HOME/fd2-run/*.DAT this whole project's tooling already
    # relies on (resolved HERE, bash-side, on purpose -- a literal "$HOME"
    # string handed in from the Python side as an already-assigned
    # positional argument would NOT get re-expanded by bash, see this
    # file's header comment on the -c argument-passing gotcha); any other
    # value = that literal path.
    local fdother=${1-}; shift || true
    local fdtxt=${1-}; shift || true
    local dato=${1-}; shift || true
    [[ "$fdother" == "" ]] && fdother="$HOME/fd2-run/FDOTHER.DAT"
    [[ "$fdtxt" == "" ]] && fdtxt="$HOME/fd2-run/FDTXT.DAT"
    [[ "$dato" == "" ]] && dato="$HOME/fd2-run/DATO.DAT"
    # remaining "$@": extra KEY=VAL env pairs, passed through verbatim.

    local sf; sf=$(state_file "$name")
    if [[ -f "$sf" ]]; then
        # shellcheck disable=SC1090
        ( source "$sf"; xvfb_alive "$XVFB_PID" ) && die "instance '$name' already running (state file $sf); teardown first"
        rm -f "$sf"
    fi

    [[ -d "$remake_dir" ]] || die "remake_dir not a directory: $remake_dir"
    [[ -x "$remake_dir/fd2-linux-verify" ]] || die "fd2-linux-verify not found/executable in $remake_dir (build it first: GOOS=linux GOARCH=amd64 go build -o fd2-linux-verify ./cmd/fd2)"

    mkdir -p "$REGISTRY_DIR"
    local port; port=$(cmd_pick_port)

    echo "[$name] starting Xvfb on :$port (1400x900x24, tcp-reachable)"
    local xvfblog="$REGISTRY_DIR/$name.xvfb.log"
    # setsid, not just nohup+disown (see the game-process comment below for
    # why plain nohup turned out to be insufficient for at least one of the
    # two process kinds this launches).
    setsid Xvfb ":$port" -screen 0 1400x900x24 -ac -nolisten local -listen tcp >"$xvfblog" 2>&1 < /dev/null &
    local xvfb_pid=$!
    disown
    sleep 1.5
    kill -0 "$xvfb_pid" 2>/dev/null || die "could not find freshly-started Xvfb pid $xvfb_pid for :$port (check $xvfblog)"
    DISPLAY="127.0.0.1:$port" xdotool getdisplaygeometry >/dev/null 2>&1 \
        || die "Xvfb on :$port did not come up (check $xvfblog)"

    local -a envargs=("FD2_CAMPAIGN=$campaign")
    [[ "$mute" == "1" ]] && envargs+=("FD2_MUTE=1")
    if [[ "$fdother" != "-" ]]; then envargs+=("FD2_ORIGINAL_FDOTHER=$fdother"); fi
    if [[ "$fdtxt" != "-" ]]; then envargs+=("FD2_ORIGINAL_FDTXT=$fdtxt"); fi
    if [[ "$dato" != "-" ]]; then envargs+=("FD2_ORIGINAL_DATO=$dato"); fi
    envargs+=("$@")

    echo "[$name] starting fd2-linux-verify in $remake_dir (env: ${envargs[*]})"
    local gamelog="$REGISTRY_DIR/$name.game.log"
    # IMPORTANT (found the hard way, 2026-09-01, this tool's own first live
    # smoke test): plain `nohup env ... ./fd2-linux-verify & disown` is NOT
    # enough to survive the launching wsl.exe/bash session closing -- unlike
    # Xvfb (which survives fine under that exact pattern), the game process
    # was repeatedly observed still alive right up until the launching
    # script/session exited, then gone a moment later with no crash/panic
    # in its own log (confirmed by a dedicated side-by-side repro: identical
    # nohup+& pattern, Xvfb survives session teardown, fd2-linux-verify does
    # not). `nohup` only makes a process ignore SIGHUP; it does not detach
    # it from the session, and this WSL2 environment's session-close
    # behavior evidently affects the two processes differently. `setsid`
    # (start the process in a brand-new session entirely, immune to
    # whatever happens to the old one) fixed it -- verified: with `setsid`,
    # the game process was still running (confirmed via a fresh `ps aux`
    # from a SEPARATE later wsl.exe invocation) after the launching session
    # had fully closed. Root cause of why nohup alone wasn't sufficient for
    # this specific binary was not fully diagnosed; setsid is the fix
    # actually verified to work, so that's what's used here. Same `cd`-in-
    # place-then-back pattern as before (so `setsid env ...` is the actual
    # exec'd process, no subshell/exec layer to lose anything through).
    local prevdir; prevdir=$(pwd)
    cd "$remake_dir" || die "cannot cd to $remake_dir"
    setsid env DISPLAY="127.0.0.1:$port" "${envargs[@]}" ./fd2-linux-verify >"$gamelog" 2>&1 < /dev/null &
    local game_pid=$!
    disown
    cd "$prevdir" || true
    # $! is reliable HERE (a real script file executing normally -- unlike
    # the wsl.exe `-c` argument-passing bug this file's header documents,
    # which only affects variable state passed *into* WSL as a -c string
    # from the Windows side; ordinary bash executing its own script body
    # has no such problem, and was confirmed correct here: setsid preserves
    # the PID across its own exec chain into env then fd2-linux-verify).
    # Still sanity-check against `ps` rather than trusting a bare number
    # blindly, and never fall back to guessing an arbitrary system-wide
    # match (this tool's own first live smoke test hit exactly that trap:
    # a naive `pgrep -f fd2-linux-verify` fallback silently adopted another
    # already-running instance's pid).
    sleep 1
    if ! kill -0 "$game_pid" 2>/dev/null || ! ps -p "$game_pid" -o args= 2>/dev/null | grep -q "fd2-linux-verify"; then
        die "fd2-linux-verify (expected pid $game_pid, from \$! right after backgrounding) is not alive/not what we expected -- check $gamelog"
    fi

    cat >"$sf" <<EOF
NAME=$name
DISPLAY_PORT=$port
XVFB_PID=$xvfb_pid
GAME_PID=$game_pid
REMAKE_DIR=$remake_dir
XVFB_LOG=$xvfblog
GAME_LOG=$gamelog
START_TIME=$(date +%s)
STATUS=starting
EOF

    echo "[$name] waiting for GLFW window on 127.0.0.1:$port ..."
    local win="" i
    for i in $(seq 1 40); do
        win=$(find_window_id "$port")
        [[ -n "$win" ]] && break
        game_alive "$game_pid" || die "fd2-linux-verify (pid $game_pid) exited before a window appeared -- check $gamelog"
        sleep 0.5
    done
    if [[ -z "$win" ]]; then
        sed -i 's/^STATUS=.*/STATUS=window_not_found/' "$sf"
        die "no GLFW window appeared within 20s (check $gamelog); state left at STATUS=window_not_found for inspection"
    fi
    sed -i 's/^STATUS=.*/STATUS=running/' "$sf"
    echo "[$name] OK port=$port xvfb_pid=$xvfb_pid game_pid=$game_pid window_id=$win"
    echo "[$name] NOTE: window just appeared -- title/opening-cutscene animation is not settled yet;"
    echo "[$name] screenshot-confirm before sending gameplay keys (same doc48 lesson as DOSBox-X side)."
}

cmd_send_key() {
    local name=${1:-}; local key=${2:-}
    [[ -n "$name" && -n "$key" ]] || die "usage: send-key <name> <xdotool-key-name>"
    load_state "$name"
    xvfb_alive "$XVFB_PID" || die "instance '$name' Xvfb is not alive"
    local win; win=$(find_window_id "$DISPLAY_PORT")
    [[ -n "$win" ]] || die "no GLFW window found for '$name' -- cannot send key blind"
    DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool key --window "$win" "$key" \
        || die "xdotool key --window $win $key failed"
    echo "[$name] sent '$key' to window $win"
}

cmd_screenshot() {
    local name=${1:-}; local out=${2:-}; local resize=${3:-}; local autocrop=${4:-}; local view_out=${5:-}
    [[ -n "$name" && -n "$out" ]] || die "usage: screenshot <name> <out_path> [resize_geometry] [autocrop:0|1] [view_out_path]"
    load_state "$name"
    xvfb_alive "$XVFB_PID" || die "instance '$name' Xvfb is not alive"
    local win; win=$(find_window_id "$DISPLAY_PORT")
    [[ -n "$win" ]] || die "no GLFW window found for '$name'"
    mkdir -p "$(dirname "$out")"
    # $out is ALWAYS the raw, untouched `import -window` capture and is never
    # modified again after this line -- 2026-09-01 (2nd pass): an earlier
    # version of this command resized/cropped $out IN PLACE, which meant the
    # true original was silently gone the moment a screenshot was taken (no
    # way to recover it for comparison if a resize/crop ever went wrong on an
    # unverified screen type). If you need the raw capture for anything, this
    # is the only file that is guaranteed to be it.
    DISPLAY="127.0.0.1:$DISPLAY_PORT" import -window "$win" "$out" \
        || die "import screenshot failed for $name (window $win)"
    echo "$out"
    [[ -n "$resize" || "$autocrop" == "1" ]] || return 0
    [[ -n "$view_out" ]] || die "resize/autocrop requested but no view_out path given"
    mkdir -p "$(dirname "$view_out")"
    cp "$out" "$view_out" || die "could not copy $out to $view_out"
    # Optional downscale: the window is captured at its real (possibly 2x/3x-
    # scaled) size, but the game's own logical canvas is a fixed 640x400
    # (remake/cmd/fd2/main.go's defaultWindowSize) -- an unscaled shot is
    # pure upscaling with zero added information, and every extra pixel is
    # extra vision-token cost for whoever reads this PNG back. `-resize
    # <geometry>` (no `!`) fits within the box preserving aspect, so passing
    # the native 640x400 on an already-1x window is a safe no-op, not a crop.
    if [[ -n "$resize" ]]; then
        convert "$view_out" -resize "$resize" "$view_out" \
            || die "resize to '$resize' failed for $name screenshot $view_out"
    fi
    # Optional autocrop: 2026-09-01 measurement found the BATTLE/map screen
    # genuinely only renders into ~79% width x ~50% height of its own logical
    # canvas (cross-checked at two different capture resolutions, same ratio
    # both times) -- the rest is a solid black margin, not information. `-trim`
    # only removes a UNIFORM-color border, so it is a safe no-op on screens
    # that already fill the frame (verified: the opening-cutscene screen has
    # zero black margin and is untouched by trim) -- this is why it is opt-in
    # rather than always-on: it has only been *confirmed* correct for the
    # battle screen, not exhaustively checked against every screen type (menus/
    # shop/dialogue), and a screen with a deliberately near-black scene could
    # in principle get over-trimmed. `+repage` resets the PNG's canvas offset
    # after trim (without it some viewers/tools keep the original canvas size
    # with the image data shifted, which defeats the whole point here).
    if [[ "$autocrop" == "1" ]]; then
        convert "$view_out" -fuzz 3% -trim +repage "$view_out" \
            || die "autocrop failed for $name screenshot $view_out"
    fi
    echo "$view_out"
}

# Generic "wait until the UI settles" primitive (doc92/doc98's animation-
# throttle lesson, made scene-agnostic): repeatedly screenshots into
# <tmp_prefix>N.png and md5-compares each against the previous one; returns
# as soon as two CONSECUTIVE shots are byte-identical, or times out.
cmd_wait_settle() {
    local name=${1:-}; local tmp_prefix=${2:-}; local max_tries=${3:-40}; local interval=${4:-0.25}
    [[ -n "$name" && -n "$tmp_prefix" ]] || die "usage: wait-settle <name> <tmp_prefix> [max_tries] [interval_seconds]"
    load_state "$name"
    xvfb_alive "$XVFB_PID" || die "instance '$name' Xvfb is not alive"
    mkdir -p "$(dirname "$tmp_prefix")"
    local win; win=$(find_window_id "$DISPLAY_PORT")
    [[ -n "$win" ]] || die "no GLFW window found for '$name'"
    local prev_md5="" cur_md5="" i shot
    for i in $(seq 1 "$max_tries"); do
        shot="${tmp_prefix}.${i}.png"
        DISPLAY="127.0.0.1:$DISPLAY_PORT" import -window "$win" "$shot" 2>/dev/null \
            || die "import screenshot failed during settle-poll (window $win)"
        cur_md5=$(md5sum "$shot" | awk '{print $1}')
        if [[ -n "$prev_md5" && "$cur_md5" == "$prev_md5" ]]; then
            echo "SETTLED tries=$i shot=$shot"
            return 0
        fi
        prev_md5=$cur_md5
        sleep "$interval"
    done
    echo "TIMEOUT tries=$max_tries last_shot=$shot"
    return 1
}

cmd_status() {
    mkdir -p "$REGISTRY_DIR"
    printf '%-14s %-10s %-8s %-8s %-8s %s\n' NAME DISPLAY XVFB_OK GAME_OK UPTIME_S GAME_LOG
    local f any=0
    for f in "$REGISTRY_DIR"/*.state; do
        [[ -e "$f" ]] || continue
        any=1
        ( # shellcheck disable=SC1090
          source "$f"
          xok="no"; xvfb_alive "$XVFB_PID" && xok="yes"
          gok="no"; game_alive "$GAME_PID" && gok="yes"
          now=$(date +%s); uptime=$((now - START_TIME))
          printf '%-14s %-10s %-8s %-8s %-8s %s\n' "$NAME" "127.0.0.1:$DISPLAY_PORT" "$xok" "$gok" "$uptime" "$GAME_LOG"
        )
    done
    [[ $any -eq 1 ]] || echo "(no fd2-live-helper instances registered)"
}

cmd_teardown() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: teardown <name>"
    local sf; sf=$(state_file "$name")
    if [[ ! -f "$sf" ]]; then echo "[$name] no state file, nothing to do"; return 0; fi
    # shellcheck disable=SC1090
    source "$sf"

    # PID+process-name verified before kill (never a blanket pkill) --
    # mirrors dosbox_harness.sh's teardown discipline exactly.
    if [[ -n "${GAME_PID:-}" ]] && kill -0 "$GAME_PID" 2>/dev/null; then
        if ps -p "$GAME_PID" -o args= 2>/dev/null | grep -q "fd2-linux-verify"; then
            echo "[$name] killing fd2-linux-verify pid $GAME_PID"
            kill "$GAME_PID" 2>/dev/null
            sleep 0.3
            kill -0 "$GAME_PID" 2>/dev/null && kill -9 "$GAME_PID" 2>/dev/null
        else
            echo "[$name] WARNING: pid $GAME_PID no longer looks like fd2-linux-verify (reused?) -- not killing"
        fi
    else
        echo "[$name] game pid $GAME_PID already gone"
    fi

    if [[ -n "${XVFB_PID:-}" ]] && kill -0 "$XVFB_PID" 2>/dev/null; then
        if ps -p "$XVFB_PID" -o args= 2>/dev/null | grep -q "Xvfb"; then
            echo "[$name] killing Xvfb pid $XVFB_PID"
            kill "$XVFB_PID" 2>/dev/null
            sleep 0.3
            kill -0 "$XVFB_PID" 2>/dev/null && kill -9 "$XVFB_PID" 2>/dev/null
        else
            echo "[$name] WARNING: pid $XVFB_PID no longer looks like Xvfb (reused?) -- not killing"
        fi
    else
        echo "[$name] Xvfb pid $XVFB_PID already gone"
    fi

    rm -f "$sf"
    echo "[$name] torn down"
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
    [[ $any -eq 1 ]] || echo "(no fd2-live-helper instances registered, nothing to tear down)"
}

main() {
    local cmd=${1:-}; shift || true
    case "$cmd" in
        pick-port)      cmd_pick_port "$@" ;;
        launch)         cmd_launch "$@" ;;
        window-id)      cmd_window_id "$@" ;;
        send-key)       cmd_send_key "$@" ;;
        screenshot)     cmd_screenshot "$@" ;;
        wait-settle)    cmd_wait_settle "$@" ;;
        status)         cmd_status "$@" ;;
        teardown)       cmd_teardown "$@" ;;
        teardown-all)   cmd_teardown_all "$@" ;;
        *)
            cat >&2 <<EOF
usage: $0 <command> [args]
  pick-port                                          auto-assign a free Xvfb display port
  launch <name> <remake_dir> <campaign> <mute:0|1> <fdother|-> <fdtxt|-> <dato|-> [K=V ...]
  window-id <name>                                   fresh xwininfo query, prints hex window id
  send-key <name> <xdotool-key-name>                 fresh window-id lookup + xdotool key --window
  screenshot <name> <out_path> [resize] [autocrop:0|1] [view_out]   raw capture always at <out_path>; -resize/-trim (if any) go to <view_out>
  wait-settle <name> <tmp_prefix> [max_tries] [interval_s]   poll until 2 consecutive shots match
  status                                              list all fd2-live-helper instances
  teardown <name>                                     kill one instance (PID+name verified)
  teardown-all                                         kill all fd2-live-helper instances
EOF
            exit 2
            ;;
    esac
}

main "$@"
