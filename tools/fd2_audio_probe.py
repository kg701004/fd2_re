#!/usr/bin/env python3
"""FD2-AUDIO-PROBE: capture the ORIGINAL game's own audio output and compare it
between screens -- an evidence path that does not depend on anyone's ears.

WHY THIS EXISTS
---------------
`91-worklist.md` carries several "曲號聽辨(使用者)" items -- identify which music track
plays where, by listening. doc12 explains why that framing is dangerous, having twice
recorded a wrong scene label that came from a listening impression:

    「曲號→場景必須溯源到呼叫點，不能憑曲風印象」

Two mechanical paths replace the ear. This tool is the second one:

  1. Read the game's own state. doc12 proved [0x51a11] holds the currently-playing
     track, and tools/fd2_dosbox_live_helper.py's `mem read-global` reads it live.
     Validated on the title screen, where it returns 18 exactly as doc12 proves.
     BUT: in-game reads returned 250 while FDMUS.DAT only holds 21 resources
     (000-020), so that path currently has an unresolved addressing problem
     (doc58 warns selectors are not stable across boot/state) -- which is precisely
     why a second, independent path is worth having.

  2. THIS TOOL: capture the audio DOSBox-X actually renders, and compare clips.
     It answers "do these two screens play the same music?" and "which FDMUS track
     does this screen's audio match?" as signal comparisons.

Capture works with no host sound card: DOSBox-X's wave capture (Ctrl+F6) taps its own
internal mixer and writes a WAV, so the historical blocker recorded in the worklist
(「容器 nosound 無法驗」) does not apply here.

STATUS -- READ THIS BEFORE USING THE SIMILARITY NUMBERS
------------------------------------------------------
CAPTURE and TIME SYNC are verified working (2026-09-03): real audio, 48kHz stereo,
14s slices bracketed by screenshots, screen-change detection live.

The IDENTIFICATION layer is NOT yet good enough, and its own control says so. Two
consecutive captures of the SAME screen playing the SAME music scored 0.917, while
that same clip scored 0.944 and 0.945 against two DIFFERENT screens. The
same-track baseline sits inside the different-track range, so a score here cannot
currently decide whether two screens share a track. Do not report these numbers as
track identity.

Why the offline selftest did not catch it: it compares synthetic pure tones, which
are trivially separable. Real FM/OPL music shares one instrument set, so different
tunes have similar average spectra, and a 14s window samples only part of a longer
piece. A selftest has to be as hard as the real signal or it validates nothing.

Fixing it needs a more discriminative feature (pitch-class/chroma profile, or
matching against the actual FDMUS_NNN tracks) and/or windows long enough to cover a
full loop. Until then this tool is a capture-and-sync rig, not an identifier.

WHAT IT DELIBERATELY DOES NOT CLAIM
-----------------------------------
Comparing clips is intended to establish SAMENESS and DIFFERENCE objectively -- see
STATUS above for why it does not yet achieve that on this material. It never names a
tune ("the majestic one"); that is a human judgement and stays one. The useful,
checkable proposition is the mapping (screen -> track identity), not the label.

TIME SYNC
---------
Each capture takes a screenshot at start and end and records both, so a clip is
anchored to a verified screen rather than to an assumption about where the game was.
If the two screenshots differ structurally the clip spans a scene change and is
flagged -- audio from a transition must not be attributed to either screen.

USAGE
-----
    python tools/fd2_audio_probe.py capture --instance vf_x --seconds 12 --label town
    python tools/fd2_audio_probe.py compare  <a.wav> <b.wav> [...]
    python tools/fd2_audio_probe.py selftest
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover
    print("ERROR: numpy required", file=sys.stderr)
    raise

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "dosbox_harness.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
OUT_ROOT = REPO_ROOT / ".wsl_build" / "audio_probe"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def wsl(argv: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    return subprocess.run(["wsl", "-d", "Ubuntu"] + argv, capture_output=True,
                          text=True, timeout=timeout, env=env)


def harness(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return wsl(["bash", HARNESS_WSL] + [str(a) for a in args], timeout=timeout)


def to_wsl(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    drive, rest = s.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


# --------------------------------------------------------------------------
# fingerprinting
# --------------------------------------------------------------------------

def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        nch, width, rate, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    if width != 2:
        raise ValueError(f"{path}: expected 16-bit PCM, got {width * 8}-bit")
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32)
    if nch > 1:
        a = a.reshape(-1, nch).mean(axis=1)
    return a / 32768.0, rate


N_BANDS = 48


def fingerprint(path: Path) -> dict:
    """Average log-spaced magnitude spectrum over the clip.

    Averaging over time deliberately throws away *when* things happen: two captures of
    the same looping track start at different points in the loop, so a time-aligned
    comparison would report them as different. What survives is the spectral character
    of the piece, which is what identity turns on here.
    """
    a, rate = read_wav_mono(path)
    if a.size < rate:                       # under a second is not a usable sample
        return {"error": f"clip too short: {a.size / rate:.2f}s", "path": str(path)}
    silent = float(np.abs(a).mean()) < 1e-4
    win = 4096
    hop = win // 2
    nfr = max(1, (a.size - win) // hop)
    acc = np.zeros(win // 2, dtype=np.float64)
    w = np.hanning(win)
    for i in range(nfr):
        seg = a[i * hop:i * hop + win]
        if seg.size < win:
            break
        acc += np.abs(np.fft.rfft(seg * w)[:win // 2])
    acc /= max(1, nfr)
    # Log-spaced bands from 40Hz to 8kHz: FM/OPL music lives well inside this.
    edges = np.geomspace(40, min(8000, rate / 2 - 1), N_BANDS + 1)
    bins = np.fft.rfftfreq(win, 1 / rate)[:win // 2]
    bands = np.array([acc[(bins >= edges[i]) & (bins < edges[i + 1])].mean()
                      if ((bins >= edges[i]) & (bins < edges[i + 1])).any() else 0.0
                      for i in range(N_BANDS)])
    norm = np.linalg.norm(bands)
    return {"path": str(path), "seconds": round(a.size / rate, 2), "rate": rate,
            "rms": round(float(np.sqrt((a ** 2).mean())), 6), "silent": silent,
            "bands": (bands / norm if norm > 0 else bands)}


def similarity(fa: dict, fb: dict) -> float:
    a, b = fa["bands"], fb["bands"]
    return float(np.dot(a, b))          # both unit-normalised -> cosine


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------

def shot(instance: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cp = harness("screenshot", instance, to_wsl(dest), timeout=120)
    return dest.exists() and "ERROR" not in (cp.stderr or "")


def cmd_capture(args) -> int:
    inst = args.instance
    out_dir = Path(args.out_dir) if args.out_dir else (OUT_ROOT / time.strftime("%Y%m%d-%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    label = args.label or inst

    before = out_dir / f"{label}_before.png"
    shot(inst, before)

    # Ctrl+F6 toggles DOSBox-X wave capture; it taps the internal mixer, so this works
    # with no host audio device.
    harness("send-keys", inst, "ctrl+F6", timeout=60)
    time.sleep(args.seconds)
    harness("send-keys", inst, "ctrl+F6", timeout=60)
    time.sleep(2)

    after = out_dir / f"{label}_after.png"
    shot(inst, after)

    # The WAV lands under the instance's own workdir (captures dir is relative to the
    # dosbox-x working directory, which the harness sets per instance).
    find = wsl(["bash", "-lc",
                f"find $HOME/fd2-run-harness-{inst} -iname '*.wav' -newermt '-{args.seconds + 120} seconds' "
                f"-printf '%T@ %p\\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-"],
               timeout=120)
    src = (find.stdout or "").strip()
    if not src:
        print(f"ERROR: no .wav appeared under ~/fd2-run-harness-{inst}. DOSBox-X wave "
              f"capture may be disabled in this build/config, or Ctrl+F6 was not "
              f"delivered (this project has a documented, unresolved key-delivery "
              f"reliability problem -- see doc58).", file=sys.stderr)
        return 2
    dest = out_dir / f"{label}.wav"
    cp = wsl(["bash", "-lc", f"cp '{src}' '{to_wsl(dest)}'"], timeout=180)
    if not dest.exists():
        print(f"ERROR: copy failed: {cp.stderr}", file=sys.stderr)
        return 2

    fp = fingerprint(dest)
    print(f"[capture] {label}: {dest}")
    print(f"          wsl source: {src}")
    if "error" in fp:
        print(f"          {fp['error']}")
    else:
        print(f"          {fp['seconds']}s  rate={fp['rate']}  rms={fp['rms']}"
              + ("   *** SILENT -- no music was playing, or capture recorded nothing" if fp["silent"] else ""))
    print(f"          screens: {before.name} / {after.name}")
    return 0


RAW_RATE, RAW_CH, RAW_WIDTH = 48000, 2, 2      # measured: 192512 B/s => 48kHz s16 stereo
RAW_BPS = RAW_RATE * RAW_CH * RAW_WIDTH


def raw_size(instance: str) -> int:
    cp = wsl(["bash", "-lc",
              f"stat -c%s $HOME/fd2-run-harness-{instance}/sdlaudio.raw 2>/dev/null || echo 0"],
             timeout=60)
    try:
        return int((cp.stdout or "0").strip())
    except ValueError:
        return 0


def cmd_rawslice(args) -> int:
    """Cut a wall-clock window out of the continuous SDL disk-audio stream.

    This is the time sync: the slice is exactly the bytes written between two
    screenshots, so the audio provably belongs to the screen those shots show. The
    stream is paced in real time by the SDL driver (do not set SDL_DISKAUDIODELAY=0 --
    see the harness), which is what makes byte offset a usable clock at all.
    """
    inst = args.instance
    out_dir = Path(args.out_dir) if args.out_dir else (OUT_ROOT / time.strftime("%Y%m%d-%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    label = args.label or inst

    before = out_dir / f"{label}_before.png"
    shot(inst, before)
    s0 = raw_size(inst)
    if s0 == 0:
        print(f"ERROR: no sdlaudio.raw for {inst}. Launch with FD2_HARNESS_AUDIO_DISK=1.",
              file=sys.stderr)
        return 2
    time.sleep(args.seconds)
    s1 = raw_size(inst)
    after = out_dir / f"{label}_after.png"
    shot(inst, after)

    # Frame-align the START. s0 is a file size, so it can land mid-frame; slicing there
    # makes every 16-bit sample straddle a byte boundary and swaps the channels -- the
    # WAV still opens and still looks fine, it is just quietly corrupt. The selftest's
    # deliberately odd-offset slice caught this (similarity to its own source stream
    # dropped to 0.827 instead of ~1.0).
    FRAME = RAW_CH * RAW_WIDTH
    if s0 % FRAME:
        s0 += FRAME - (s0 % FRAME)
    nbytes = (s1 - s0) - ((s1 - s0) % FRAME)
    if nbytes < RAW_BPS:                       # under a second of audio
        print(f"ERROR: only {nbytes} bytes accumulated in {args.seconds}s -- the stream "
              f"is not advancing (is the instance running?)", file=sys.stderr)
        return 2
    dest_raw = out_dir / f"{label}.raw"
    # bs=1 here would copy a byte at a time and take minutes for a multi-megabyte
    # offset -- measured as an apparent hang. skip_bytes/count_bytes let the offset
    # stay exact while the block size stays sane.
    cp = wsl(["bash", "-lc",
              f"dd if=$HOME/fd2-run-harness-{inst}/sdlaudio.raw of='{to_wsl(dest_raw)}' "
              f"bs=1M iflag=skip_bytes,count_bytes skip={s0} count={nbytes} status=none"],
             timeout=600)
    if not dest_raw.exists() or dest_raw.stat().st_size == 0:
        print(f"ERROR: slice failed: {cp.stderr}", file=sys.stderr)
        return 2
    dest = out_dir / f"{label}.wav"
    pcm = dest_raw.read_bytes()
    pcm = pcm[:len(pcm) - (len(pcm) % (RAW_CH * RAW_WIDTH))]
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(RAW_CH); w.setsampwidth(RAW_WIDTH); w.setframerate(RAW_RATE)
        w.writeframes(pcm)
    dest_raw.unlink()

    # Time sync check: if the screen changed structurally mid-window the clip spans a
    # transition and must not be attributed to either screen.
    moved = ""
    try:
        # Import by path, not spec_from_file_location: that module defines dataclasses,
        # and @dataclass looks the class's module up in sys.modules, which a
        # module_from_spec module is not registered in -- it fails with a confusing
        # "'NoneType' object has no attribute '__dict__'".
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        import fd2_original_verify as v
        kind, info = v.classify_instability([before, after])
        moved = f"   screen during window: {kind} ({info})"
        if kind == "structural":
            moved += "\n   *** WARNING: the screen CHANGED during this window -- this clip " \
                     "spans a transition, do not attribute it to either screen"
    except Exception as e:  # noqa: BLE001
        moved = f"   (screen-change check unavailable: {e})"

    fp = fingerprint(dest)
    print(f"[rawslice] {label}: {dest}")
    print(f"           bytes {s0}..{s1} ({nbytes}) = {nbytes / RAW_BPS:.2f}s of stream")
    if "error" in fp:
        print(f"           {fp['error']}")
    else:
        print(f"           {fp['seconds']}s rate={fp['rate']} rms={fp['rms']}"
              + ("   *** SILENT" if fp["silent"] else ""))
    print(moved)
    return 0


def cmd_compare(args) -> int:
    fps = []
    for p in args.wavs:
        f = fingerprint(Path(p))
        if "error" in f:
            print(f"SKIP {p}: {f['error']}", file=sys.stderr)
            continue
        fps.append(f)
    if len(fps) < 2:
        print("need at least two usable clips", file=sys.stderr)
        return 2
    names = [Path(f["path"]).stem for f in fps]
    w = max(len(n) for n in names) + 1
    print(" " * w + "".join(f"{n[:9]:>10s}" for n in names))
    for i, fa in enumerate(fps):
        row = f"{names[i]:{w}s}"
        for fb in fps:
            row += f"{similarity(fa, fb):10.3f}"
        print(row)
    print()
    print("1.000 = identical spectrum. Interpret with the silence/rms column: two silent")
    print("clips also correlate perfectly and mean nothing.")
    for f in fps:
        print(f"  {Path(f['path']).stem:20s} {f['seconds']:6.1f}s  rms={f['rms']:.6f}"
              + ("   SILENT" if f["silent"] else ""))
    return 0


def cmd_selftest(args) -> int:
    """Offline: prove the fingerprint discriminates before trusting any capture."""
    import tempfile
    ok = fail = 0

    def check(name, cond, detail=""):
        nonlocal ok, fail
        print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if not cond else ""))
        if cond: ok += 1
        else: fail += 1

    def write_tone(path, freqs, seconds=3.0, rate=22050, phase=0.0):
        t = np.arange(int(rate * seconds)) / rate
        a = sum(np.sin(2 * math.pi * f * t + phase) for f in freqs) / len(freqs)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes((a * 20000).astype("<i2").tobytes())

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        write_tone(d / "a.wav", [440, 880])
        write_tone(d / "a2.wav", [440, 880], phase=1.1)   # same tune, different offset
        write_tone(d / "b.wav", [523, 1319])              # different tune
        fa, fa2, fb = fingerprint(d / "a.wav"), fingerprint(d / "a2.wav"), fingerprint(d / "b.wav")
        s_same, s_diff = similarity(fa, fa2), similarity(fa, fb)
        check("same tune at a different loop offset scores high", s_same > 0.95, f"{s_same:.3f}")
        check("a different tune scores lower", s_diff < s_same - 0.05, f"same={s_same:.3f} diff={s_diff:.3f}")
        # A silent clip must be reported as silent, or two silences would "match".
        with wave.open(str(d / "s.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(np.zeros(22050 * 3, dtype="<i2").tobytes())
        check("silence is flagged", fingerprint(d / "s.wav")["silent"] is True)
        check("audible clip is not flagged silent", fa["silent"] is False)

        # --- raw-stream slicing maths, offline -------------------------------
        # rawslice cuts a byte range out of a continuously-written PCM stream and wraps
        # it as a WAV. Get the frame alignment or the rate wrong and every clip is
        # subtly corrupt while still *looking* fine, so check it against a synthetic
        # stream whose content is known.
        rate, ch, wd = RAW_RATE, RAW_CH, RAW_WIDTH
        secs = 4.0
        t = np.arange(int(rate * secs)) / rate
        tone = (np.sin(2 * math.pi * 300 * t) * 20000).astype("<i2")
        stereo = np.repeat(tone, ch)                       # interleaved L=R
        raw_path = d / "stream.raw"
        raw_path.write_bytes(stereo.tobytes())
        check("byte rate matches 48kHz/2ch/16bit", RAW_BPS == 192000, str(RAW_BPS))
        check("synthetic stream length matches the byte-rate clock",
              abs(raw_path.stat().st_size / RAW_BPS - secs) < 0.01,
              f"{raw_path.stat().st_size / RAW_BPS:.3f}s vs {secs}s")
        # Slice a 2s window starting 1s in, deliberately at an ODD byte offset to prove
        # the frame-alignment trim is doing its job.
        FRAME = ch * wd
        s0 = int(1.0 * RAW_BPS) + 1            # deliberately mid-frame, as a real size can be
        s0_aligned = s0 + (FRAME - s0 % FRAME) % FRAME
        n = int(2.0 * RAW_BPS)
        n -= n % FRAME
        pcm = raw_path.read_bytes()[s0_aligned:s0_aligned + n]
        sl = d / "slice.wav"
        with wave.open(str(sl), "wb") as w:
            w.setnchannels(ch); w.setsampwidth(wd); w.setframerate(rate)
            w.writeframes(pcm)
        fs = fingerprint(sl)
        check("slice duration matches the requested window",
              abs(fs["seconds"] - 2.0) < 0.02, f"{fs['seconds']}s")
        check("slice is not silent", fs["silent"] is False)
        # And the slice must still be recognisably the same signal as the whole stream.
        whole = d / "whole.wav"
        with wave.open(str(whole), "wb") as w:
            w.setnchannels(ch); w.setsampwidth(wd); w.setframerate(rate)
            w.writeframes(raw_path.read_bytes())
        s_self = similarity(fingerprint(whole), fs)
        check("a slice matches the stream it came from", s_self > 0.95, f"{s_self:.3f}")
        # Control: a slice of a DIFFERENT stream must not match, or the check above
        # would pass for any two clips.
        other = (np.sin(2 * math.pi * 1700 * t) * 20000).astype("<i2")
        op = d / "other.wav"
        with wave.open(str(op), "wb") as w:
            w.setnchannels(ch); w.setsampwidth(wd); w.setframerate(rate)
            w.writeframes(np.repeat(other, ch).tobytes())
        s_other = similarity(fingerprint(op), fs)
        check("a different stream does NOT match", s_other < s_self - 0.05,
              f"same={s_self:.3f} other={s_other:.3f}")
        # The control that gives the alignment check its teeth: slicing from the
        # UNALIGNED offset must score measurably worse, or "aligned" proves nothing.
        bad = raw_path.read_bytes()[s0:s0 + n]
        bad = bad[:len(bad) - (len(bad) % FRAME)]
        bp = d / "unaligned.wav"
        with wave.open(str(bp), "wb") as w:
            w.setnchannels(ch); w.setsampwidth(wd); w.setframerate(rate)
            w.writeframes(bad)
        s_bad = similarity(fingerprint(whole), fingerprint(bp))
        check("an UNALIGNED slice scores worse (so alignment is load-bearing)",
              s_bad < s_self - 0.02, f"aligned={s_self:.3f} unaligned={s_bad:.3f}")
    print(f"\nselftest: {'PASS' if not fail else 'FAIL'} ({ok} ok, {fail} failed)")
    return 0 if not fail else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("capture", help="record the instance's audio to a WAV, anchored by "
                                        "a screenshot before and after")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--seconds", type=float, default=12.0)
    sp.add_argument("--label", default=None)
    sp.add_argument("--out-dir", default=None)
    sp.set_defaults(func=cmd_capture)

    sp = sub.add_parser("rawslice", help="cut a wall-clock window out of the continuous SDL "
                                         "disk-audio stream, bracketed by screenshots (needs "
                                         "the instance launched with FD2_HARNESS_AUDIO_DISK=1)")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--seconds", type=float, default=12.0)
    sp.add_argument("--label", default=None)
    sp.add_argument("--out-dir", default=None)
    sp.set_defaults(func=cmd_rawslice)

    sp = sub.add_parser("compare", help="pairwise spectral similarity across clips")
    sp.add_argument("wavs", nargs="+")
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("selftest", help="offline checks. NOTE: these use synthetic tones "
                                          "and are known to be EASIER than the real signal -- "
                                          "passing them does not mean the fingerprint can "
                                          "identify game music (see module STATUS)")
    sp.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
