#!/usr/bin/env python3
"""fd2_re - send a key and PROVE it arrived, instead of hoping a fixed wait was enough.

Why this exists
---------------
Every live round in this project loses time to silently dropped keys: a sweep
that looks complete but only registered one press, an end-turn that never
happened, a chord that produced nothing. On 2026-09-07 a batch of three
end-turns registered exactly one, and it was only caught because the turn
counter was read afterwards. `fd2_dosbox_live_helper.py key --settle` polls
until the screen stops changing, which is a different question: it says "the
screen is quiet now", not "my key was acted on".

What this does
--------------
`press` watches a caller-named REGION of the screen: it first takes two frames
with no key in between to prove that region is static, then sends the key and
retries while the region is unchanged. A change in a provably-static region is a
direct observation that the guest reacted.

The region is not optional decoration. The first version compared whole frames
and its own negative control failed immediately -- FD2's screens animate, so any
two frames differ and every key, bound or not, looked "confirmed".

Three honest limits, all of which the caller must think about:

1. **A key can legitimately change nothing.** Pressing Right at the right edge
   of a grid, or Confirm on a refused target, leaves the screen identical, and
   this tool will keep retrying and then report `confirmed=False`. Use
   `--allow-no-change` for those, and treat the result as "sent", not "acted on".

2. **Pick the region deliberately.** It has to respond to the key AND be static
   otherwise. If it animates, `press` returns `confirmed: None` and says so
   rather than handing back a meaningless True.

3. **Toggles.** A retry on a toggle (the deployment grid's Confirm, say) will
   turn the cell back off. Never retry a toggle blindly -- press once, then read
   the state that is supposed to have changed (a counter, a colour) instead.

Usage
-----
    python tools/fd2_verified_input.py --instance ai2 --keys "up,up,left"
    python tools/fd2_verified_input.py --instance ai2 --keys confirm --retries 4
    python tools/fd2_verified_input.py --instance ai2 --selftest
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HELPER = Path(__file__).resolve().parent / "fd2_dosbox_live_helper.py"


def _helper(*args: str, timeout: int = 240) -> str:
    r = subprocess.run([sys.executable, str(HELPER), *args],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def _shot(instance: str, tag: str) -> Path:
    out = Path(f".wsl_build/{instance}/vin_{tag}.png")
    _helper("screenshot", "--instance", instance, "--autocrop", "--out", str(out))
    return Path(str(out).replace(".png", "_view.png"))


def _same(a: Path, b: Path, region: tuple[int, int, int, int] | None = None) -> bool:
    from PIL import Image, ImageChops  # noqa: PLC0415
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if region:
        ia, ib = ia.crop(region), ib.crop(region)
    return ImageChops.difference(ia, ib).getbbox() is None


def press(instance: str, key: str, retries: int = 3, wait: float = 2.0,
          allow_no_change: bool = False,
          region: tuple[int, int, int, int] | None = None) -> dict:
    """Send `key` and verify the guest reacted, by watching `region`.

    The first version compared the WHOLE frame, and its own negative control
    caught the flaw immediately: FD2's town screen animates (sprites, banners),
    so two consecutive frames differ with no input at all and every key looked
    "confirmed". Whole-frame comparison is therefore only valid on a screen that
    is genuinely static, which most of this game's screens are not.

    So the caller names a region that (a) responds to the key and (b) does not
    animate, and this function first PROVES (b) by taking two frames with no key
    in between. If that baseline already differs, the region is unusable and the
    result says so rather than returning a meaningless True.
    """
    base_a = _shot(instance, "base_a")
    base_b = _shot(instance, "base_b")
    if not _same(base_a, base_b, region):
        return {"key": key, "confirmed": None,
                "note": ("the watched area changes on its own (animation), so a change "
                         "after the key would prove nothing -- pass a --region that is "
                         "static on this screen")}
    for attempt in range(1, retries + 1):
        _helper("key", "--instance", instance, key, "--wait", str(wait), "--no-require-change")
        after = _shot(instance, "after")
        if not _same(base_b, after, region):
            return {"key": key, "confirmed": True, "attempts": attempt}
        if allow_no_change:
            return {"key": key, "confirmed": False, "attempts": attempt,
                    "note": "no change, accepted because --allow-no-change"}
    return {"key": key, "confirmed": False, "attempts": retries,
            "note": "the watched area never changed -- the key may have been dropped, or it "
                    "legitimately does nothing here (see this tool's docstring)"}


# The town's location-label plate: responds to a direction key (the label text
# changes) and does not animate. Coordinates are in the autocropped 640x407 view.
TOWN_LABEL_REGION = (495, 345, 640, 400)


def selftest(instance: str) -> int:
    """Run from a town screen. A direction key must change the location label --
    and the paired negative control is that the SAME check must report no change
    for a key the game ignores, so a tool that always answered 'confirmed' fails
    here. That control is what caught the first version's whole-frame comparison
    being meaningless on this game's animated screens."""
    fails = []
    print("(1) a direction key must change the town location label")
    r = press(instance, "right", region=TOWN_LABEL_REGION)
    print(f"    {'PASS' if r['confirmed'] else 'FAIL'}: {r}")
    if not r["confirmed"]:
        fails.append("direction key produced no screen change")

    print("\n(2) negative control: a key the game does not bind must NOT be confirmed")
    r = press(instance, "F7", retries=2, region=TOWN_LABEL_REGION)
    print(f"    {'PASS' if not r['confirmed'] else 'FAIL'}: {r}")
    if r["confirmed"]:
        fails.append("an unbound key was reported as confirmed -- the check is not "
                     "actually measuring the guest's reaction")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed (1 forward + 1 negative control).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--keys", help="comma-separated keys, sent in order")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--wait", type=float, default=2.0)
    ap.add_argument("--allow-no-change", action="store_true")
    ap.add_argument("--region", help="x0,y0,x1,y1 area to watch (required on animated screens)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.instance)
    if not a.keys:
        ap.error("need --keys or --selftest")
    rc = 0
    for k in [x.strip() for x in a.keys.split(",") if x.strip()]:
        reg = tuple(int(x) for x in a.region.split(",")) if a.region else None
        r = press(a.instance, k, a.retries, a.wait, a.allow_no_change, reg)
        print(r)
        if not r["confirmed"] and not a.allow_no_change:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
