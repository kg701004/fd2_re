#!/usr/bin/env bash
# Bash companion for tools/fd2_dosbox_live_helper.py -- WRAPS the existing
# tools/dosbox_harness.sh (N-way parallel dosbox-x/heavy-debugger harness,
# docs/knowledge-base/98-tooling-infrastructure.md's "N-way 平行 dosbox-x
# live-verification harness" section) rather than reimplementing any of its
# launch/teardown/registry core -- every subcommand below either (a) shells
# out to dosbox_harness.sh's own subcommand for the primitive it needs, or
# (b) reads dosbox_harness.sh's existing per-instance state file (same
# REGISTRY_DIR/TMUX_SOCKET constants, read via the same env var overrides)
# for the handful of new capabilities dosbox_harness.sh does not itself
# provide (settle-confirmed waiting, live-memory-dump convenience,
# canonical-file integrity check).
#
# ARCHITECTURE -- why this is a separate .sh file, invoked as real argv,
# never a Python-built multi-statement `bash -c "stmt1;stmt2"` string: this
# project hit a genuine, reproducible bug building the sibling remake-side
# tool (tools/fd2_live_input_helper.py/.sh, 2026-09-01) where exactly that
# pattern silently drops shell variable state between statements when passed
# through wsl.exe from the Windows side (full repro in that tool's own
# header comment and docs/knowledge-base/98-tooling-infrastructure.md's
# dated 2026-09-01 section). The fix used there -- and reused here from the
# start -- is a real .sh file invoked with plain positional argv
# (`wsl -d Ubuntu bash <this file> <subcommand> <arg1> ...`), exactly the
# pattern tools/dosbox_harness.sh itself has always used. Every WSL-side call
# from fd2_dosbox_live_helper.py goes through this file for exactly that
# reason -- do not "simplify" a future change back into an inline -c string.
#
# Usage:
#   fd2_dosbox_live_helper.sh launch <name> [keepalive_seconds]
#       -- thin wrapper around dosbox_harness.sh launch: prints a ONE-LINE,
#          NON-BLOCKING warning if the canonical dir's FD2.EXE doesn't match
#          the known-pristine hash (see verify-canonical), then execs
#          straight into dosbox_harness.sh launch (same long-lived foreground
#          semantics -- caller must background this call exactly like
#          dosbox_harness.sh's own launch requires, see that file's header).
#   fd2_dosbox_live_helper.sh key <name> <key> [key2 ...]
#       -- thin passthrough to dosbox_harness.sh send-keys (no wait/settle of
#          its own -- fd2_dosbox_live_helper.py's `key` subcommand owns the
#          wait-vs-settle decision and calls wait-settle below itself,
#          mirroring the remake-side template's split between "send" and
#          "confirm").
#   fd2_dosbox_live_helper.sh screenshot <name> <out_path> [resize] [autocrop:0|1] [view_out_path]
#       -- wraps dosbox_harness.sh screenshot (which does `import -window
#          root` -- the WHOLE Xvfb virtual screen, not just the dosbox-x
#          window). <out_path> is ALWAYS that raw, untouched capture, exactly
#          as dosbox_harness.sh produced it -- never modified after the fact
#          (same discipline fd2_live_input_helper.sh's screenshot enforces,
#          after a real bug in an earlier version of THAT tool overwrote the
#          raw capture in place, see its own header + doc98's 續四). If
#          resize/autocrop is requested, the processed copy goes to
#          <view_out_path> instead. autocrop here is a TWO-STEP process,
#          deliberately different from fd2_live_input_helper.sh's single
#          fuzzy -trim (see cmd_screenshot below for the empirical reasoning
#          -- doc98's dated 2026-09-02 section has the full writeup with
#          concrete before/after numbers).
#   fd2_dosbox_live_helper.sh wait-settle <name> <tmp_prefix> [max_tries] [interval_seconds] [baseline_screenshot_path]
#       -- NEW capability, not in dosbox_harness.sh: polls via repeated calls
#          to dosbox_harness.sh screenshot, md5-compares each against the
#          previous one, returns as soon as 2 CONSECUTIVE shots match (or
#          times out). This is a MITIGATION for, not a fix to, this
#          project's known Xvfb/xdotool/DOSBox-X input-reliability problem
#          (docs/knowledge-base/58-remake-live-verification-log.md 續七十~
#          續七十七, 9 dedicated investigation rounds, doc58's own conclusion
#          is "已重新定界的環境限制" -- a re-scoped environment limitation,
#          not solved). Do not oversell what this does: it confirms the
#          SCREEN stopped visibly changing, it does not confirm any specific
#          keystroke was received.
#          Optional [baseline_screenshot_path] (2026-09-02): a screenshot
#          taken BEFORE the key was sent. If given, the settled frame's md5
#          is compared against it and a `response=NO_RESPONSE`/`response=
#          CHANGED` tag is appended to the SETTLED output line -- a
#          best-effort "this key send produced literally zero visible
#          change" flag, NOT proof the key was dropped (some keys legitimately
#          produce no change, e.g. a movement key at a map edge). Callers
#          should log/flag NO_RESPONSE, not auto-treat it as failure.
#   fd2_dosbox_live_helper.sh debugger-status <name> [baseline_screenshot_path]
#       -- NEW: best-effort check of whether the ncurses debugger TUI looks
#          active in the instance's tmux pane (greps for "Code Overview",
#          confirmed marker per docs/knowledge-base/48-dosbox-x-debugger-
#          build.md §4.1/§8). Alt+Pause (dosbox_harness.sh enter-debugger) is
#          a TOGGLE -- this exists so callers can check state before firing
#          it blind and accidentally exiting the debugger they meant to
#          enter.
#          Optional [baseline_screenshot_path] (2026-09-02): a screenshot
#          taken at a known moment (e.g. right when the debugger was
#          entered). If given, a fresh screenshot is compared against it and
#          a SCREEN_CHECK line is appended -- directly answers "is it really
#          still paused" for the documented stale-pane blind spot (a
#          genuinely paused emulator's own window cannot repaint; a CHANGED
#          screenshot while the pane still says ACTIVE means the pane is
#          stale, not that execution is paused).
#   fd2_dosbox_live_helper.sh resume <name>
#       -- NEW 2026-09-02: reliably resume execution from the debugger by
#          typing its own "RUN" console command, instead of a second
#          Alt+Pause toggle -- built after that toggle's "exit" direction
#          was observed to fail silently several times in a row in a real
#          session (see docs/knowledge-base/92-m5-normal-playthrough-log.md
#          續十四/續十六). No-op (does not send RUN) if the pane doesn't
#          currently look like the debugger TUI.
#   fd2_dosbox_live_helper.sh mem-dump <name> <selector_hex> <linear_hex> <bytecount_hex> <out_path>
#       -- NEW: packages the proven byte-signature/MEMDUMPBIN live-memory-
#          read technique (docs/knowledge-base/48-dosbox-x-debugger-build.md,
#          docs/knowledge-base/58-remake-live-verification-log.md's many
#          MEMDUMPBIN rounds, and the fd2-dosbox-live-memory-extraction
#          project-memory reference) into one push-button call: issues
#          `MEMDUMPBIN <selector> <linear> <bytecount>` via
#          dosbox_harness.sh debugger-cmd, waits for MEMDUMP.BIN to appear in
#          the instance's own workdir, copies it to <out_path>. Bakes in the
#          two sharpest documented footguns (see cmd_mem_dump below): a
#          zero/empty selector is refused outright (doc58: silently returns
#          garbage, not an error), and a missing output file after the
#          command was sent is reported as the KNOWN DOSBox-X upstream bug
#          it almost certainly is (GitHub issue #3629), not swallowed as a
#          generic failure.
#   fd2_dosbox_live_helper.sh verify-canonical [path]
#       -- NEW: md5sums FD2.EXE (+ FD2.EXE.pristine_bak if present) at <path>
#          (default $HOME/fd2-run) against the known-pristine hash and
#          reports PASS/MISMATCH loudly. Read-only: NEVER writes, restores,
#          or otherwise touches either file, under any circumstance --
#          ~/fd2-run/FD2.EXE is CURRENTLY KNOWN to be in a deliberately
#          patched state for an unrelated, still-active ch27 investigation
#          thread (docs/knowledge-base/92-m5-normal-playthrough-log.md 續八/
#          續九), and this check exists to make that visible, not to "fix" it.
#   fd2_dosbox_live_helper.sh enter-debugger <name>
#   fd2_dosbox_live_helper.sh debugger-cmd <name> <cmd text...>
#   fd2_dosbox_live_helper.sh status [stale_after_seconds]
#       -- passthrough to dosbox_harness.sh status, PLUS (NEW 2026-09-02) a
#          STALE warning line for any instance at/above stale_after_seconds
#          uptime (default: dosbox_harness.sh's own KEEPALIVE_DEFAULT,
#          3600s) -- exists because this project already mistook a ~13h-old
#          orphaned instance for a fresh one once (docs/knowledge-base/
#          92-m5-normal-playthrough-log.md, Phase 4 round 2). Advisory only,
#          never auto-tears-down anything.
#   fd2_dosbox_live_helper.sh teardown <name>
#   fd2_dosbox_live_helper.sh teardown-all
#       -- straight passthroughs to the matching dosbox_harness.sh subcommand
#          (kept here so callers only ever need to know about ONE script).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOSBOX_HARNESS="$SCRIPT_DIR/dosbox_harness.sh"

# Mirrors dosbox_harness.sh's own constants exactly (same env var override
# names) so this tool reads state files it did not itself create, and so a
# customized registry/tmux-socket stays consistent between both tools. This
# is NOT a reimplementation of dosbox_harness.sh's launch/teardown logic --
# just enough to locate and read the state file it already writes.
REGISTRY_DIR="${FD2_HARNESS_REGISTRY_DIR:-$HOME/.fd2-harness/instances}"
TMUX_SOCKET="${FD2_HARNESS_TMUX_SOCKET:-fd2harness}"

# Known-pristine FD2.EXE hash (verified against 3 independent backups
# 2026-08-19/2026-09-02: ~/fd2-run/FD2.EXE.pristine_bak,
# C:\Users\kg701\Desktop\GAME\FD2\FD2.EXE, and the project-memory record of
# the earlier FD2_USB/FD2_APK\FD2_old.EXE comparison -- see
# docs/knowledge-base/92-m5-normal-playthrough-log.md 續八/續九).
PRISTINE_FD2_EXE_MD5="33464c81e6a364fd0660141139aa8e6e"

die() { echo "ERROR: $*" >&2; exit 1; }

state_file() { echo "$REGISTRY_DIR/$1.state"; }

load_state() {
    local name=$1
    local sf; sf=$(state_file "$name")
    [[ -f "$sf" ]] || die "no such dosbox_harness.sh instance: $name (no state file at $sf -- launch it first via this tool's own launch subcommand, or dosbox_harness.sh launch directly)"
    # shellcheck disable=SC1090
    source "$sf"
}

# --------------------------------------------------------------------------
# Thin passthroughs -- do not reinvent dosbox_harness.sh's own logic.
# --------------------------------------------------------------------------

cmd_key() {
    local name=${1:-}; shift || true
    [[ -n "$name" && $# -gt 0 ]] || die "usage: key <name> <key> [key2 ...]"
    bash "$DOSBOX_HARNESS" send-keys "$name" "$@"
}

cmd_enter_debugger() { bash "$DOSBOX_HARNESS" enter-debugger "$@"; }
cmd_debugger_cmd()   { bash "$DOSBOX_HARNESS" debugger-cmd "$@"; }
cmd_teardown()       { bash "$DOSBOX_HARNESS" teardown "$@"; }
cmd_teardown_all()   { bash "$DOSBOX_HARNESS" teardown-all "$@"; }

# dosbox_harness.sh's own KEEPALIVE_DEFAULT (see that file) -- mirrored here
# as the default staleness threshold for the STALE warning below. Not a
# claim that any instance older than this is definitely abandoned (a real
# Phase-4-style long playthrough can legitimately run past its own default
# keepalive if launched with an explicit larger --keepalive) -- just the
# same "the harness's own idea of a normal session length" line dosbox_
# harness.sh itself uses, surfaced as a nudge to check rather than assume.
STALE_UPTIME_DEFAULT_S=3600

# --------------------------------------------------------------------------
# status -- passthrough to dosbox_harness.sh status, PLUS a stale-instance
# warning (2026-09-02, NEW here, not in dosbox_harness.sh itself). Exists
# because this project has already hit a real incident of exactly this kind
# (docs/knowledge-base/92-m5-normal-playthrough-log.md's Phase 4 round 2: a
# ~13h-old orphaned instance was mistaken for a fresh one at the start of a
# round, briefed as clean when it was not). This does NOT auto-teardown
# anything -- only flags it, since a genuinely long-running deliberate
# session (large --keepalive) looks identical in the state file to a
# forgotten one; only a human/agent who remembers what they launched can
# tell the difference.
# --------------------------------------------------------------------------

cmd_status() {
    local stale_after=${1:-$STALE_UPTIME_DEFAULT_S}
    local out; out=$(bash "$DOSBOX_HARNESS" status)
    echo "$out"
    local header_skipped=0 line name uptime
    while IFS= read -r line; do
        if [[ $header_skipped -eq 0 ]]; then header_skipped=1; continue; fi
        [[ "$line" == "(no harness instances registered)" || -z "$line" ]] && continue
        name=$(awk '{print $1}' <<<"$line")
        uptime=$(awk '{print $7}' <<<"$line")
        if [[ "$uptime" =~ ^[0-9]+$ && "$uptime" -ge "$stale_after" ]]; then
            echo "STALE: instance '$name' uptime=${uptime}s >= ${stale_after}s (default mirrors dosbox_harness.sh's own KEEPALIVE_DEFAULT) -- confirm this is an intentional long-running session (explicit large --keepalive) before assuming it's a fresh boot; NOT auto-torn-down, verify with a screenshot/debugger-status before 'teardown $name' if unsure."
        fi
    done <<<"$out"
}

# --------------------------------------------------------------------------
# launch -- wraps dosbox_harness.sh launch with a non-blocking pristine-file
# warning. Deliberately `exec`s into dosbox_harness.sh's own launch (which
# ends in a long `exec sleep $keepalive` itself) so the long-lived foreground
# process semantics that subcommand REQUIRES (doc48 §8.4 "續四十六的教訓":
# an extra layer of backgrounding around it gets the whole Xvfb/tmux/
# dosbox-x tree reaped by WSLg within 15-60s) are fully preserved -- this
# wrapper adds a print statement before the exec, nothing else.
# --------------------------------------------------------------------------

cmd_launch() {
    local name=${1:-}
    [[ -n "$name" ]] || die "usage: launch <name> [keepalive_seconds]"
    local source_dir="${FD2_HARNESS_SOURCE_DIR:-$HOME/fd2-run}"
    if [[ -f "$source_dir/FD2.EXE" ]]; then
        local h; h=$(md5sum "$source_dir/FD2.EXE" 2>/dev/null | awk '{print $1}')
        if [[ -n "$h" && "$h" != "$PRISTINE_FD2_EXE_MD5" ]]; then
            echo "WARNING: $source_dir/FD2.EXE md5=$h does not match the known-pristine hash ($PRISTINE_FD2_EXE_MD5) -- the canonical game dir may be in a deliberately-patched state from an unrelated investigation thread; run '$0 verify-canonical' for details. This is INFORMATIONAL ONLY, launch proceeds unmodified." >&2
        fi
    fi
    exec bash "$DOSBOX_HARNESS" launch "$@"
}

# --------------------------------------------------------------------------
# screenshot -- see this file's header comment + fd2_dosbox_live_helper.py's
# module docstring for the full empirical writeup (doc98 2026-09-02 dated
# section has the concrete numbers). Summary of what's different from the
# remake-side template's --autocrop and why:
#
#   dosbox_harness.sh's screenshot is `import -window root`: it captures the
#   WHOLE Xvfb virtual screen (1024x768 in this project's launch config),
#   not just the dosbox-x window -- so the raw capture legitimately includes
#   real desktop background OUTSIDE the game window (unlike the remake
#   tool's `import -window <id>`, which only ever captured the game's own
#   window to begin with). Two independent things are worth stripping here,
#   and they need two different techniques:
#
#   1. The Xvfb desktop background surrounding the dosbox-x window -- this
#      background is measured pure black (#000000, same as much of the
#      game's own UI), so a bare `-fuzz 3% -trim` heuristic CANNOT reliably
#      tell "outside the window" from "inside the window, genuinely black
#      content" (verified 2026-09-02: on a title/load-save-list screenshot,
#      a bare -trim shrank 640x417 down to 640x413 -- it ate 4 real, if
#      content-free, pixel rows off the BOTTOM of the actual dosbox-x
#      window, not just the surrounding desktop). The safe, deterministic
#      fix used here is a FRESH `xdotool getwindowgeometry` query (same
#      "always re-query, never cache" discipline as this project's other
#      window-id lookups) and an exact `-crop WxH+X+Y`, not a color
#      heuristic -- confirmed 2026-09-02 to reproduce the dosbox-x window's
#      real bounding box exactly (640x417 at position 192,184) on 3
#      independent screenshots.
#   2. dosbox-x's OWN persistent GUI menu bar (Main/CPU/Video/Sound/DOS/
#      Drive/Capture/Debug/Help -- confirmed doc98 finding: windowed dosbox-x
#      always draws this, unlike plain `dosbox`, REGARDLESS of scaler/aspect
#      settings) is real window content, a constant ~17px tall, that a
#      window-bounds crop alone will not remove. A second, best-effort
#      `-fuzz 3% -trim` pass on top of the geometry-cropped image can strip
#      it (and confirmed 2026-09-02: the game's own content fills its full
#      640x400 canvas with NO internal letterboxing on all 3 screen types
#      tested -- pre-title cutscene, title menu, load-save list -- so there
#      is no remake-style "black margin within the game canvas" to find
#      here, only the menu bar). Only verified on those 3 screen types, not
#      exhaustively on battle HUD/shop/dialogue, so -- same discipline as
#      fd2_live_input_helper.sh's own --autocrop -- this second pass is
#      opt-in via the SAME --autocrop flag, not a separate one, and the
#      window-bounds crop (step 1, always safe) runs first either way when
#      --autocrop is given.
#
#   --resize has NO forced default here (unlike fd2_live_input_helper.sh's
#   640x400): DOSBox-X mixes a 320x200-mode-doubled-to-640x400 canvas AND a
#   native 640x400 SVGA cutscene canvas behind the SAME non-scaling 17px
#   menu bar within one tool, so there is no single "shrink 2x, zero
#   information lost" operation that is valid for every screen type the way
#   there was for the remake's fixed logical canvas -- pass an explicit
#   geometry only when you know the specific screen's native size.
# --------------------------------------------------------------------------

cmd_screenshot() {
    local name=${1:-}; local out=${2:-}; local resize=${3:-}; local autocrop=${4:-}; local view_out=${5:-}
    [[ -n "$name" && -n "$out" ]] || die "usage: screenshot <name> <out_path> [resize] [autocrop:0|1] [view_out]"
    mkdir -p "$(dirname "$out")"
    bash "$DOSBOX_HARNESS" screenshot "$name" "$out" >/dev/null \
        || die "dosbox_harness.sh screenshot failed for $name"
    echo "$out"
    [[ -n "$resize" || "$autocrop" == "1" ]] || return 0
    [[ -n "$view_out" ]] || die "resize/autocrop requested but no view_out path given"
    mkdir -p "$(dirname "$view_out")"
    cp "$out" "$view_out" || die "could not copy $out to $view_out"

    if [[ "$autocrop" == "1" ]]; then
        load_state "$name"
        local win geo pos wh x y
        win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
        [[ -n "$win" ]] || die "autocrop requested but no DOSBox window found for $name on 127.0.0.1:$DISPLAY_PORT -- cannot compute crop geometry"
        geo=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool getwindowgeometry "$win")
        pos=$(echo "$geo" | grep -oP 'Position:\s*\K[0-9]+,[0-9]+')
        wh=$(echo "$geo" | grep -oP 'Geometry:\s*\K[0-9]+x[0-9]+')
        [[ -n "$pos" && -n "$wh" ]] || die "could not parse xdotool getwindowgeometry output for $name: $geo"
        x=${pos%,*}; y=${pos#*,}
        # Step 1: exact, deterministic crop to the real window bounding box.
        convert "$view_out" -crop "${wh}+${x}+${y}" +repage "$view_out" \
            || die "window-bounds crop (${wh}+${x}+${y}) failed for $name screenshot $view_out"
        # Step 2: best-effort fuzzy trim on top, to also strip the menu bar /
        # any real uniform margin, if present (see header comment above).
        convert "$view_out" -fuzz 3% -trim +repage "$view_out" \
            || die "fuzzy trim pass failed for $name screenshot $view_out"
    fi
    if [[ -n "$resize" ]]; then
        convert "$view_out" -resize "$resize" "$view_out" \
            || die "resize to '$resize' failed for $name screenshot $view_out"
    fi
    echo "$view_out"
}

# --------------------------------------------------------------------------
# wait-settle -- generic "poll until the screen stops changing" primitive,
# built entirely on top of dosbox_harness.sh's own screenshot subcommand
# (never reimplements the `import` capture itself). See this file's header
# comment for the honest scope statement (mitigation, not a fix, for the
# project's known input-reliability problem).
# --------------------------------------------------------------------------

cmd_wait_settle() {
    local name=${1:-}; local tmp_prefix=${2:-}; local max_tries=${3:-40}; local interval=${4:-0.25}; local baseline=${5:-}
    [[ -n "$name" && -n "$tmp_prefix" ]] || die "usage: wait-settle <name> <tmp_prefix> [max_tries] [interval_seconds] [baseline_screenshot_path]"
    mkdir -p "$(dirname "$tmp_prefix")"
    # Optional no-response flag (2026-09-02): if a baseline screenshot (taken
    # BEFORE the key was sent) is given, compare its md5 against the FINAL
    # settled frame's md5. Equal => the screen never visibly changed across
    # this whole key-send, which is the observable symptom this project's
    # known input-reliability problem produces (doc58 續七十~續七十七) --
    # surfaced as a `response=NO_RESPONSE` tag so a caller can flag/log it
    # instead of silently treating "settled" as "the key worked". This is
    # still a MITIGATION-level signal, not proof: some keys legitimately
    # produce no visible change (e.g. a movement key at a map edge, or a key
    # with no binding on the current screen) -- a caller must not treat
    # NO_RESPONSE as an automatic failure, only as something worth a second
    # look.
    local baseline_md5=""
    if [[ -n "$baseline" ]]; then
        [[ -f "$baseline" ]] || die "baseline screenshot not found: $baseline"
        baseline_md5=$(md5sum "$baseline" | awk '{print $1}')
    fi
    local prev_md5="" cur_md5="" i shot
    for i in $(seq 1 "$max_tries"); do
        shot="${tmp_prefix}.${i}.png"
        bash "$DOSBOX_HARNESS" screenshot "$name" "$shot" >/dev/null 2>&1 \
            || die "screenshot failed during settle-poll (instance $name)"
        cur_md5=$(md5sum "$shot" | awk '{print $1}')
        if [[ -n "$prev_md5" && "$cur_md5" == "$prev_md5" ]]; then
            local resp=""
            if [[ -n "$baseline_md5" ]]; then
                if [[ "$cur_md5" == "$baseline_md5" ]]; then
                    resp=" response=NO_RESPONSE"
                else
                    resp=" response=CHANGED"
                fi
            fi
            echo "SETTLED tries=$i shot=$shot${resp}"
            return 0
        fi
        prev_md5=$cur_md5
        sleep "$interval"
    done
    echo "TIMEOUT tries=$max_tries last_shot=$shot"
    return 1
}

# --------------------------------------------------------------------------
# debugger-status -- best-effort check of whether the ncurses debugger TUI
# is currently showing in the instance's tmux pane. "Code Overview" is a
# confirmed marker string (docs/knowledge-base/48-dosbox-x-debugger-
# build.md §4.1: "tmux pane 截到完整 ncurses TUI(Code Overview / Output
# 視窗 + `I->` 提示字元)"). Exists because Alt+Pause (dosbox_harness.sh
# enter-debugger) TOGGLES the debugger -- calling it blind when already
# inside the debugger would exit it, not enter it.
# --------------------------------------------------------------------------

cmd_debugger_status() {
    local name=${1:-}; local baseline=${2:-}
    [[ -n "$name" ]] || die "usage: debugger-status <name> [baseline_screenshot_path]"
    load_state "$name"
    local pane pane_active=0
    pane=$(tmux -L "$TMUX_SOCKET" capture-pane -t "$TMUX_SESSION" -p 2>/dev/null) \
        || die "could not capture tmux pane for $name (session $TMUX_SESSION, socket $TMUX_SOCKET) -- is the instance still alive? check 'dosbox_harness.sh status'"
    if echo "$pane" | grep -q "Code Overview"; then
        pane_active=1
        # CAVEAT confirmed live 2026-09-02: this can be a FALSE POSITIVE. The
        # ncurses debugger TUI does not appear to repaint the tmux pty after
        # RUN resumes (the game's own rendering goes to the SDL/X11 window,
        # not this pane) -- toggling OUT of the debugger a second time and
        # immediately re-checking was observed to still report ACTIVE, with
        # the exact same frozen EAX/EIP/cc= values as the prior paused state.
        # Treat "ACTIVE" as "the debugger TUI was drawn here at some point
        # and nothing has since produced different pane content", not as
        # live proof execution is currently paused -- if in doubt, cross-
        # check against a screenshot (a resumed game repaints its own
        # window immediately) rather than trusting this alone.
        echo "ACTIVE: ncurses debugger TUI detected ('Code Overview' found in tmux pane) -- NOTE: this pane can go stale after leaving the debugger (confirmed 2026-09-02, see this command's source comment); cross-check with a screenshot if you need to be sure execution is still actually paused, not just that the TUI was drawn here at some point"
    else
        echo "INACTIVE: no 'Code Overview' text in tmux pane -- looks like the normal DOS/log console, not the debugger TUI. Call 'dosbox_harness.sh enter-debugger $name' to toggle it, then check this command again before assuming it worked (Alt+Pause is asynchronous and can occasionally land mid-transition, doc48 §4.1)."
    fi

    # Optional screenshot cross-check (2026-09-02), reusing the same
    # baseline-compare idea as wait-settle's response=NO_RESPONSE/CHANGED
    # flag: a genuinely PAUSED emulator's own SDL/X11 window cannot repaint
    # (that's what "paused" means), so if the caller supplies a screenshot
    # taken at a KNOWN moment (e.g. right when the debugger was entered),
    # comparing it against a fresh one now directly answers the "is it
    # really still paused" question this command's pane-text check alone
    # cannot -- exactly the blind spot documented above.
    if [[ -n "$baseline" ]]; then
        [[ -f "$baseline" ]] || die "baseline screenshot not found: $baseline"
        local tmp; tmp=$(mktemp --suffix=.png)
        bash "$DOSBOX_HARNESS" screenshot "$name" "$tmp" >/dev/null 2>&1 \
            || die "screenshot failed during debugger-status baseline check for $name"
        local b_md5 c_md5
        b_md5=$(md5sum "$baseline" | awk '{print $1}')
        c_md5=$(md5sum "$tmp" | awk '{print $1}')
        rm -f "$tmp"
        if [[ "$b_md5" == "$c_md5" ]]; then
            if [[ $pane_active -eq 1 ]]; then
                echo "SCREEN_CHECK: unchanged vs baseline -- consistent with genuinely still paused"
            else
                echo "SCREEN_CHECK: unchanged vs baseline -- consistent with INACTIVE too (just no visible progress since baseline, e.g. a static screen); not proof either way on its own"
            fi
        else
            if [[ $pane_active -eq 1 ]]; then
                echo "SCREEN_CHECK: CHANGED vs baseline -- CONTRADICTS the pane's 'ACTIVE' reading. This is the documented stale-pane blind spot above -- trust the screenshot: execution has almost certainly actually resumed."
            else
                echo "SCREEN_CHECK: CHANGED vs baseline -- consistent with INACTIVE (game genuinely progressing, not paused)"
            fi
        fi
    fi
}

# --------------------------------------------------------------------------
# resume -- reliably resume execution from the debugger. NEW 2026-09-02,
# built live after Alt+Pause's "exit debugger" direction failed silently
# several times in a row during a real investigation session (debugger TUI
# stayed up -- `I->` prompt still showing in the tmux pane -- while its
# "enter" direction stayed reliable throughout; see docs/knowledge-base/
# 92-m5-normal-playthrough-log.md's 2026-09-02 續十四/續十六 sections for
# the live incidents this was built to fix). The working alternative found
# live: type the debugger's OWN "RUN" console command (the same mechanism
# `debugger-cmd` already uses) instead of depending on the Alt+Pause hotkey
# toggle a second time.
#
# Only acts when the pane currently looks like the debugger TUI ("Code
# Overview" found) -- if it doesn't, assumes execution is already running
# and does nothing (harmless either way: dosbox-x's normal DOS console pane
# does not treat stray "RUN" text as a command outside the debugger, but
# skipping it is still cleaner and faster, and avoids polluting the pane's
# scrollback with a no-op).
#
# KNOWN LIMITATION, confirmed live 2026-09-02: the same stale-pane blind
# spot documented on cmd_debugger_status above also affects THIS check --
# "Code Overview" text can still be sitting in the pane's scrollback well
# after execution has genuinely resumed, so this command can send a
# redundant RUN even when already running. Confirmed harmless in practice
# (sending RUN again while already running does not break or re-pause
# anything, verified via `resume --verify` called twice in a row against a
# live instance) -- the tradeoff (occasionally redundant but always safe)
# is intentional, not a bug to fix.
# --------------------------------------------------------------------------

cmd_resume() {
    local name=${1:-}
    [[ -n "$name" ]] || die "usage: resume <name>"
    load_state "$name"
    local pane
    pane=$(tmux -L "$TMUX_SOCKET" capture-pane -t "$TMUX_SESSION" -p 2>/dev/null) \
        || die "could not capture tmux pane for $name (session $TMUX_SESSION, socket $TMUX_SOCKET) -- is the instance still alive? check 'dosbox_harness.sh status'"
    if echo "$pane" | grep -q "Code Overview"; then
        tmux -L "$TMUX_SOCKET" send-keys -t "$TMUX_SESSION" -l "RUN"
        sleep 0.3
        tmux -L "$TMUX_SOCKET" send-keys -t "$TMUX_SESSION" -l $'\r'
        echo "[$name] pane showed debugger TUI -- sent RUN console command to resume execution"
    else
        echo "[$name] pane does not show debugger TUI -- assuming already running, no action taken (if you suspect the pane is stale rather than genuinely running, screenshot-diff to confirm instead of forcing another RUN)"
    fi
}

# --------------------------------------------------------------------------
# mem-dump -- packages the proven byte-signature/MEMDUMPBIN live-memory-read
# technique into one push-button call. See this file's header comment and
# fd2_dosbox_live_helper.py's module docstring for the full citation trail.
# --------------------------------------------------------------------------

cmd_mem_dump() {
    local name=${1:-}; local selector=${2:-}; local linear=${3:-}; local bytecount=${4:-}; local out=${5:-}
    [[ -n "$name" && -n "$selector" && -n "$linear" && -n "$bytecount" && -n "$out" ]] \
        || die "usage: mem-dump <name> <selector_hex> <linear_hex> <bytecount_hex> <out_path>"

    # Footgun #1 (doc58, e.g. line ~2445/~23 of the fd2-dosbox-live-memory-
    # extraction project-memory reference): a selector of 0 (or empty) does
    # NOT error -- it silently resolves to an invalid/null selector and
    # MEMDUMPBIN returns garbage that LOOKS like a successful dump. Refuse
    # it outright rather than let that happen quietly.
    local sel_clean; sel_clean=$(echo "$selector" | tr '[:upper:]' '[:lower:]' | sed 's/^0x//')
    if [[ -z "$sel_clean" || "$sel_clean" =~ ^0+$ ]]; then
        die "selector '$selector' is zero/empty -- this is a KNOWN failure mode, not a typo you can safely ignore: MEMDUMPBIN with selector 0 silently returns garbage instead of erroring (doc58's fd2-dosbox-live-memory-extraction reference, and 58-remake-live-verification-log.md's own record of this exact mistake). Read the REAL flat selector from the debugger's Register Overview or GDT after entering the debugger (this project has seen 0170/0178 for FD2.EXE, but per doc58 續四十 do not assume it is stable across a fresh boot -- verify it this session, every session)."
    fi

    load_state "$name"

    # Best-effort debugger-active check (see cmd_debugger_status) -- warn,
    # don't hard-fail, since a caller who already knows the TUI is up (e.g.
    # scripted from a round that just entered it) shouldn't be blocked by a
    # flaky tmux capture-pane read.
    local pane
    pane=$(tmux -L "$TMUX_SOCKET" capture-pane -t "$TMUX_SESSION" -p 2>/dev/null || true)
    if ! echo "$pane" | grep -q "Code Overview"; then
        echo "WARNING: tmux pane for $name does not currently show the debugger TUI ('Code Overview' not found) -- MEMDUMPBIN will do nothing useful if sent to the normal DOS console. Run 'debugger-status $name' to confirm, or 'dosbox_harness.sh enter-debugger $name' first if you haven't. Proceeding anyway." >&2
    fi

    # Always exactly 3 positional args to MEMDUMPBIN (selector, linear,
    # bytecount) -- this structurally rules out the OTHER documented
    # MEMDUMPBIN footgun (doc58 ~line 2445: a dropped argument silently
    # shifts everything and produces a fixed 1048576-byte dump starting from
    # linear address 0). That failure mode came from a human hand-typing the
    # debugger command with an argument missing; going through this wrapper
    # cannot reproduce it since all 3 fields are required parameters.
    rm -f "$WORKDIR/MEMDUMP.BIN"
    bash "$DOSBOX_HARNESS" debugger-cmd "$name" "MEMDUMPBIN $selector $linear $bytecount" \
        || die "debugger-cmd failed sending MEMDUMPBIN to $name"

    local i
    for i in $(seq 1 20); do
        [[ -f "$WORKDIR/MEMDUMP.BIN" ]] && break
        sleep 0.25
    done
    if [[ ! -f "$WORKDIR/MEMDUMP.BIN" ]]; then
        die "MEMDUMPBIN command was sent but $WORKDIR/MEMDUMP.BIN never appeared after 5s. This matches a KNOWN DOSBox-X upstream bug (GitHub issue #3629: MEMDUMPBIN can report success in the debugger console without actually writing a file -- documented in this project at 58-remake-live-verification-log.md 續四十九/續五十). Workaround this tool does NOT automate: use the debugger's 'D <selector>:<linear_hex>' data-view command instead (reads ~112 bytes per call, 48-dosbox-x-debugger-build.md §4.2/§8.4) via 'debugger-cmd $name \"D ...\"' + 'debugger-status $name' to read the TUI text back."
    fi

    local sz; sz=$(stat -c%s "$WORKDIR/MEMDUMP.BIN")
    mkdir -p "$(dirname "$out")"
    cp "$WORKDIR/MEMDUMP.BIN" "$out" || die "could not copy $WORKDIR/MEMDUMP.BIN to $out"
    echo "$out"
    echo "SIZE=$sz"
    if [[ "$sz" == "1048576" ]]; then
        echo "WARNING: output is exactly 1048576 bytes (0x100000) -- this is the doc58-documented signature of a MEMDUMPBIN call that fell back to dumping 1MB from linear address 0 (normally caused by a missing/malformed argument reaching the debugger console). Treat this dump as suspect, not real data at the address you asked for." >&2
    fi
}

# --------------------------------------------------------------------------
# verify-canonical -- read-only integrity check. NEVER writes/restores
# anything, under any circumstance. See this file's header comment.
# --------------------------------------------------------------------------

cmd_verify_canonical() {
    local path="${1:-$HOME/fd2-run}"
    [[ -d "$path" ]] || die "not a directory: $path"
    echo "verify-canonical: checking $path (read-only -- this command never writes/restores anything)"
    local status_overall=0
    local exe="$path/FD2.EXE"
    if [[ -f "$exe" ]]; then
        local h; h=$(md5sum "$exe" | awk '{print $1}')
        if [[ "$h" == "$PRISTINE_FD2_EXE_MD5" ]]; then
            echo "  FD2.EXE: OK (md5=$h matches pristine)"
        else
            echo "  FD2.EXE: MISMATCH md5=$h (expected pristine $PRISTINE_FD2_EXE_MD5)"
            echo "    -- this file may be intentionally patched by an active investigation thread"
            echo "       (docs/knowledge-base/92-m5-normal-playthrough-log.md 續八/續九); this check"
            echo "       NEVER modifies or restores it. Do not trust readings from this copy for"
            echo "       anything outside that specific thread without confirming the patch is the"
            echo "       one you expect."
            status_overall=1
        fi
    else
        echo "  FD2.EXE: NOT FOUND at $exe"
        status_overall=1
    fi
    local bak="$path/FD2.EXE.pristine_bak"
    if [[ -f "$bak" ]]; then
        local hb; hb=$(md5sum "$bak" | awk '{print $1}')
        if [[ "$hb" == "$PRISTINE_FD2_EXE_MD5" ]]; then
            echo "  FD2.EXE.pristine_bak: OK (md5=$hb matches pristine)"
        else
            echo "  FD2.EXE.pristine_bak: WARNING md5=$hb does NOT match the expected pristine hash -- this backup itself may be compromised, treat with suspicion, do not assume it is safe to restore from"
            status_overall=1
        fi
    else
        echo "  FD2.EXE.pristine_bak: not present at $bak (nothing to cross-check against here)"
    fi
    exit $status_overall
}

main() {
    local cmd=${1:-}; shift || true
    case "$cmd" in
        launch)            cmd_launch "$@" ;;
        key)                cmd_key "$@" ;;
        screenshot)         cmd_screenshot "$@" ;;
        wait-settle)        cmd_wait_settle "$@" ;;
        debugger-status)    cmd_debugger_status "$@" ;;
        resume)             cmd_resume "$@" ;;
        mem-dump)           cmd_mem_dump "$@" ;;
        verify-canonical)   cmd_verify_canonical "$@" ;;
        enter-debugger)     cmd_enter_debugger "$@" ;;
        debugger-cmd)       cmd_debugger_cmd "$@" ;;
        status)             cmd_status "$@" ;;
        teardown)           cmd_teardown "$@" ;;
        teardown-all)       cmd_teardown_all "$@" ;;
        *)
            cat >&2 <<EOF
usage: $0 <command> [args]
  launch <name> [keepalive_seconds]        dosbox_harness.sh launch + non-blocking pristine-FD2.EXE warning
  key <name> <key> [key2 ...]              passthrough to dosbox_harness.sh send-keys
  screenshot <name> <out> [resize] [autocrop:0|1] [view_out]   raw always at <out>; window-bounds-crop (+optional fuzzy trim)/resize (if any) go to <view_out>
  wait-settle <name> <tmp_prefix> [max_tries] [interval_s] [baseline]   poll until 2 consecutive shots match (mitigation, not a fix, for known input-reliability issue); optional baseline screenshot adds response=NO_RESPONSE/CHANGED
  debugger-status <name> [baseline]          best-effort check of whether the ncurses debugger TUI is showing; optional baseline screenshot adds a SCREEN_CHECK cross-check
  resume <name>                              reliably resume from the debugger via its own RUN console command (fixes Alt+Pause's flaky "exit" direction); no-op if pane doesn't look paused
  mem-dump <name> <selector_hex> <linear_hex> <bytecount_hex> <out_path>   MEMDUMPBIN wrapper with known-footgun guards
  verify-canonical [path]                   md5 integrity check vs known-pristine FD2.EXE (default \$HOME/fd2-run); READ-ONLY, never restores
  enter-debugger <name>                     passthrough to dosbox_harness.sh
  debugger-cmd <name> <text...>             passthrough to dosbox_harness.sh
  status [stale_after_seconds]              passthrough to dosbox_harness.sh status + STALE warning for old instances (default threshold 3600s)
  teardown <name>                           passthrough to dosbox_harness.sh
  teardown-all                              passthrough to dosbox_harness.sh
EOF
            exit 2
            ;;
    esac
}

main "$@"
