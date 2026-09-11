#!/usr/bin/env python3
"""Export editable acting behaviour from a decoder transcript.

The input is the human-readable output of ``decode_acting.py``.  It contains
only a decoded account of a runtime resource table; this exporter writes an
editable JSON frame set (beat count, special flag, original roster slot and
pose), never original bytes, pointers, or executable data.

Example:

    python3 tools/export_acting_resource_set.py \
      extracted/dosbox_dump/acting_decoded/acting_decoded_throne.txt \
      remake/assets/cutscenes/acting/map32.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


HEADER = re.compile(r"^=== acting id 0x([0-9a-fA-F]+) \(ptr=.*\) ===$")
FRAME = re.compile(
    r"^\s+frame\[(\d+)\] 拍數=(\d+) \[bit7=(0|1)[^]]*\] N=(\d+):(?: (.*))?$"
)
UNIT = re.compile(r"\(unit=(\d+),pose=(\d+)\)")


def parse(path: Path) -> dict[str, list[dict[str, object]]]:
    """Parse complete decoder sections, rejecting truncated/malformed frames."""

    resources: dict[str, list[dict[str, object]]] = {}
    current: int | None = None
    expected: int | None = None
    frames: list[dict[str, object]] = []

    def finish() -> None:
        nonlocal current, expected, frames
        if current is None:
            return
        if expected is None or len(frames) != expected:
            raise ValueError(
                f"acting id {current} has {len(frames)} frames, expected {expected}"
            )
        resources[str(current)] = frames
        current, expected, frames = None, None, []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        header = HEADER.match(raw_line)
        if header:
            finish()
            current = int(header.group(1), 16)
            continue
        if current is None:
            continue
        if "(指標超出本輪 dump 範圍" in raw_line:
            current, expected, frames = None, None, []
            continue
        if "帧数=" in raw_line:
            matched = re.search(r"帧数=(\d+)", raw_line)
            if matched is None:
                raise ValueError(f"cannot parse frame count: {raw_line!r}")
            expected = int(matched.group(1))
            continue
        frame = FRAME.match(raw_line)
        if frame is None:
            continue
        if expected is None:
            raise ValueError(f"acting id {current} has frame before declared count")
        index, beats, bit7, declared_units, pairs = frame.groups()
        if int(index) != len(frames):
            raise ValueError(f"acting id {current} frame index {index} is not contiguous")
        units = [
            {"slot": int(slot), "pose": int(pose)}
            for slot, pose in UNIT.findall(pairs or "")
        ]
        if len(units) != int(declared_units):
            raise ValueError(
                f"acting id {current} frame {index} has {len(units)} units, expected {declared_units}"
            )
        item: dict[str, object] = {"beats": int(beats), "units": units}
        if bit7 == "1":
            item["special"] = True
        frames.append(item)
    finish()
    if not resources:
        raise ValueError(f"no complete acting resources found in {path}")
    return dict(sorted(resources.items(), key=lambda item: int(item[0])))


def selftest() -> int:
    """這支的 docstring 宣稱「rejecting truncated/malformed frames」——那是一句
    **可以被驗證的宣稱**,而不是一句願望。它有 5 條拒絕路徑,每一條都對應一種
    「靜默解出錯誤動畫」的失敗:frame 數與宣告不符、frame 出現在宣告之前、
    index 不連續、unit 數與宣告不符、frame 數解析不出來。

    正向那半同樣重要:合法輸入必須真的解出資源,否則「全部拒絕」也會通過。
    """
    import sys
    import tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    good = (
        "=== acting id 0x1a (ptr=0x1234) ===\n"
        "帧数=2\n"
        "  frame[0] 拍數=3 [bit7=0 待機] N=2: (unit=1,pose=0) (unit=2,pose=1)\n"
        "  frame[1] 拍數=4 [bit7=1 動作] N=1: (unit=3,pose=2)\n"
    )

    def run(text):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.txt"
            p.write_text(text, encoding="utf-8")
            return parse(p)

    print("(1) 正向:合法轉錄必須解出資源、frame 與 unit 都對")
    got = run(good)
    ok1 = (list(got) == ["26"] and len(got["26"]) == 2
           and got["26"][0]["units"] == [{"slot": 1, "pose": 0}, {"slot": 2, "pose": 1}]
           and len(got["26"][1]["units"]) == 1)
    print(f"    {'PASS' if ok1 else 'FAIL'}: id {list(got)}、frames "
          f"{[len(v) for v in got.values()]}、首幀 units {got.get('26', [{}])[0].get('units')}")
    if not ok1:
        fails.append(f"正向解析錯誤:{got}")

    print("\n(2) 五條拒絕路徑,每一條都必須真的丟 ValueError")
    cases = [
        ("frame 數少於宣告",
         good.replace("  frame[1] 拍數=4 [bit7=1 動作] N=1: (unit=3,pose=2)\n", "")),
        ("frame 出現在宣告之前",
         "=== acting id 0x1a (ptr=0x0) ===\n"
         "  frame[0] 拍數=3 [bit7=0 待機] N=0:\n"),
        ("index 不連續",
         good.replace("frame[1]", "frame[5]")),
        ("unit 數與宣告不符",
         good.replace("N=2: (unit=1,pose=0) (unit=2,pose=1)", "N=3: (unit=1,pose=0)")),
        ("frame 數解析不出來",
         good.replace("帧数=2", "帧数=abc")),
    ]
    for label, text in cases:
        try:
            run(text)
            print(f"    FAIL: 「{label}」沒有被拒絕")
            fails.append(f"{label} 沒有被拒絕")
        except ValueError:
            print(f"    PASS: 「{label}」-> ValueError")
        except Exception as exc:                              # noqa: BLE001
            print(f"    FAIL: 「{label}」丟出 {type(exc).__name__}")
            fails.append(f"{label} 丟出 {type(exc).__name__} 而非 ValueError")

    print("\n(3) 「指標超出本輪 dump 範圍」的區段必須被整段丟棄,而不是半解半留")
    partial = (good.replace("帧数=2", "帧数=2\n  (指標超出本輪 dump 範圍)")
               + "=== acting id 0x2b (ptr=0x9) ===\n帧数=1\n"
                 "  frame[0] 拍數=1 [bit7=0 待機] N=0:\n")
    got3 = run(partial)
    ok3 = "26" not in got3 and "43" in got3
    print(f"    {'PASS' if ok3 else 'FAIL'}: 解出 {sorted(got3)}(超範圍的 26 應被丟棄、43 應保留)")
    if not ok3:
        fails.append(f"超範圍區段處理錯誤:{sorted(got3)}")

    print("\n(4) 空輸入必須丟錯,而不是回空 dict")
    # 2026-09-08:第一版我預期空輸入回 `{}`,是讀錯了契約 —— 它丟
    # ValueError("no complete acting resources found")。而且那是**比較好的**行為:
    # 空的轉錄幾乎必然代表上游 dump 失敗,靜默回 {} 會讓呼叫端寫出一個空 JSON,
    # 然後在很遠的地方才發現動畫沒了。釘住真實契約,不是我以為的那個。
    try:
        got4 = run("")
        ok4, shown = False, repr(got4)
    except ValueError as exc:
        ok4, shown = True, str(exc)[:50]
    print(f"    {'PASS' if ok4 else 'FAIL'}: {shown}")
    if not ok4:
        fails.append(f"空輸入回傳 {shown} 而非丟錯")

    print("\n(5) 非恆真控制:上面全都丟錯也會「通過」,所以再確認正向那半仍解得出東西")
    ok5 = len(run(good)) == 1
    print(f"    {'PASS' if ok5 else 'FAIL'}: 合法轉錄解出 {len(run(good))} 個資源")
    if not ok5:
        fails.append("合法轉錄解不出資源")

    print("\n(6) bit7 旗標:bit7=1 的 frame 必須帶 special=True,bit7=0 的不得帶這個鍵")
    # 2026-09-12 突變窮舉:`if bit7 == "1"` 與 `item["special"] = True` 改掉都逃掉 ——
    # (1) 只核對 units,沒看旗標。前提:good 的 frame[0] 是 bit7=0、frame[1] 是 bit7=1。
    fr = run(good)["26"]
    ok6 = "special" not in fr[0] and fr[1].get("special") is True
    print(f"    {'PASS' if ok6 else 'FAIL'}: frame[0] {sorted(fr[0])}、frame[1] special={fr[1].get('special')!r}")
    if not ok6:
        fails.append(f"bit7 旗標對應錯誤:{fr}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向 + 5 條拒絕路徑 + 超範圍丟棄 + 空輸入契約 + "
          "非恆真控制)。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?",
                        help="decode_acting.py text transcript")
    parser.add_argument("output", type=Path, nargs="?",
                        help="editable acting-resource JSON")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.input is None or args.output is None:
        parser.error("需要 input 與 output(或用 --selftest)")

    result = {"schema_version": 1, "resources": parse(args.input)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"exported {len(result['resources'])} acting resources -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
