#!/usr/bin/env python3
"""fd2_re - feed every byte-level decoder truncated and corrupt input, and require it not to crash.

Why this exists
---------------
2026-09-08. Writing a "output length always equals w×h" invariant for
`decode_sprite.py` immediately produced an `IndexError`: mode 0 read its value
byte with `body[i]` and no bounds check, while modes 2/3 used slicing and
tolerated truncation. One function, one kind of bad input, two behaviours — one
of them a crash. **36 real sub-resources in this repo hit it.**

The same shape then turned up in `decode_lmi.py` and, found by running rather
than by reading, in `decode_dato.py` (10 of 401 truncation lengths) and
`decode_ani.py` (no positional bound at all, plus a zero-length run that makes
no progress). Four decoders, one bug class.

A grep for `x = buf[i]` finds these but also flags every correctly-guarded loop
whose bound lives in the `while` header — 29 hits, mostly false. Execution is
the ground truth, so this tool *runs* each decoder against every prefix of real
data and against corrupted bytes, and requires that nothing escapes but the
exceptions the decoder declares.

What "robust" means here
------------------------
Not "returns the right pixels" — a truncated resource has no right answer. It
means: **degrade, do not crash**. The caller of a decoder in this repo is
usually a batch loop over hundreds of sub-resources (`extract_all.py`,
`export_sprites.py`); one `IndexError` there kills the whole run, and the
failure looks like "the tool is broken" rather than "this one resource is
short".

Registered decoders declare which exceptions are legitimate (a container parser
is *supposed* to reject a non-container). Anything else is a finding.

Usage
-----
    python tools/verify_truncation_robustness.py
    python tools/verify_truncation_robustness.py --steps 200   # 更密的截斷取樣
    python tools/verify_truncation_robustness.py --selftest
"""

from __future__ import annotations

import argparse
import importlib
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "extracted" / "raw"
GAME = ROOT / "org_game" / "炎龍騎士團" / "FLAME2"


def _sample(subdir: str, limit: int = 600) -> bytes:
    d = RAW / subdir
    if not d.is_dir():
        return b""
    for fn in sorted(os.listdir(d)):
        p = d / fn
        if p.is_file() and p.stat().st_size > 32:
            return p.read_bytes()[:limit]
    return b""


def _dat(name: str, limit: int = 600) -> bytes:
    p = GAME / name
    return p.read_bytes()[:limit] if p.is_file() else b""


# (模組, 函式, 說明, 取樣資料, 由 body 組出呼叫引數, 合法例外)
# 「合法例外」是這支解碼器**宣告**它會丟的:容器 parser 本來就該拒絕非容器。
# 其餘任何例外都是發現 —— 特別是 IndexError / struct.error 這種「讀過頭」的。
DECODERS = [
    ("decode_sprite", "decode_rle_sprite", "24×24 sprite RLE(EXE 0x4EB52)",
     lambda: _sample("FIGANI"), lambda b: ((b, 24, 24), {}), ()),
    ("decode_lmi", "decode_pixels", "LMI1 像素 codec(EXE 0x4e916)",
     lambda: _sample("FDOTHER"), lambda b: ((b, 576), {}), ()),
    ("decode_image", "decode_rle", "通用 RLE(第 2 輪破解)",
     lambda: _sample("BG"), lambda b: ((b, 576), {}), ()),
    ("decode_dato", "rle", "DATO 幀 RLE",
     lambda: _sample("DATO"), lambda b: ((b, 576), {}), ()),
    ("decode_ani", "rle_2mode", "ANI opcode 2/6 的 2-mode RLE",
     lambda: _sample("ANI"), lambda b: ((b, 0, bytearray(576), 0, 576), {}), ()),
    ("decode_figani", "decode_rle", "FIGANI 戰鬥動畫 RLE(24×24 文法的變體)",
     lambda: _sample("FIGANI"), lambda b: ((b, 24, 24), {}), ()),
    ("render_map", "_tile_rle", "地圖 tile RLE(native 0x4deda)",
     lambda: _sample("FDSHAP"), lambda b: ((b, 24, 24), {}), ()),
    ("unpack_dat", "parse_directory", "LLLLLL 容器目錄",
     lambda: _dat("ANI.DAT"), lambda b: ((b,), {}), ("NotAContainer", "error")),
    ("decode_lmi", "lmi_offsets", "LMI1 目錄",
     lambda: _sample("FDOTHER"), lambda b: ((b,), {}), ("NotLMI", "error")),
]


def _call(mod, fn, body, mk):
    m = importlib.import_module(mod)
    f = getattr(m, fn)
    args, kw = mk(body)
    return f(*args, **kw)


def probe(entry, steps: int, seed: int = 0) -> dict:
    mod, fn, desc, get, mk, allowed = entry
    body = get()
    if not body:
        return {"tool": f"{mod}.{fn}", "desc": desc, "verdict": "SKIP",
                "detail": "找不到取樣資料"}
    rng = random.Random(seed * 7919 + len(body))
    bad: dict[str, int] = {}
    n_tested = 0

    def run(blob):
        nonlocal n_tested
        n_tested += 1
        try:
            _call(mod, fn, blob, mk)
        except Exception as exc:                              # noqa: BLE001
            name = type(exc).__name__
            if name not in allowed:
                bad[name] = bad.get(name, 0) + 1

    # (1) 每一個前綴長度(含 0)。截斷是真實情況:FIGANI 用的是另一參數化變體,
    #     套用 24×24 文法會提早耗盡。
    # 2026-09-08:這裡原本等距抽 `steps` 個切點,結果 `decode_figani.decode_rle`
    # 被判 OK —— 但它的模式 0/1 明明沒有邊界守衛。崩潰只發生在「控制位元組剛好是
    # 最後一個 byte」那幾個特定長度,等距抽樣直接跳過。`decode_dato` 當初是用逐一
    # 長度掃出來的(401 個裡 10 個),換成抽樣就會漏。截斷是一維且有界的維度,
    # 沒有理由抽樣:取樣資料改成上限 600 byte,用窮舉換掉抽樣。
    # `steps` 只留給位元翻轉(那個空間太大,只能抽樣)。
    for c in range(len(body) + 1):
        run(body[:c])
    # (2) 位元翻轉:截斷之外,損壞的控制位元組會走到不同分支。
    for _ in range(steps):
        blob = bytearray(body[:max(8, len(body) // 4)])
        for _ in range(rng.randint(1, 4)):
            blob[rng.randrange(len(blob))] = rng.randrange(256)
        run(bytes(blob))
    # (3) 全 0xC0 / 全 0xFF:專打 run 長度為 0 或極大的路徑。
    for filler in (b"\xC0", b"\xFF", b"\x00"):
        run(filler * 64)

    return {"tool": f"{mod}.{fn}", "desc": desc,
            "verdict": "CRASH" if bad else "OK",
            "detail": (f"{n_tested} 次呼叫,非預期例外 {bad}" if bad
                       else f"{n_tested} 次呼叫全部安全返回")}


def selftest() -> int:
    fails = []

    print("(1) 故障注入:一個刻意沒有邊界檢查的解碼器必須被判為 CRASH")
    probe_mod = Path(__file__).with_name("zz_trunc_probe.py")
    probe_mod.write_text(
        '"""測試用:刻意沒有邊界檢查。"""\n'
        "def fragile(body, total):\n"
        "    out = bytearray(); i = 0\n"
        "    while len(out) < total and i < len(body):\n"
        "        c = body[i]; i += 1\n"
        "        if c > 0xC0:\n"
        "            v = body[i]; i += 1          # 沒有守衛\n"
        "            out += bytes([v]) * (c - 0xC0)\n"
        "        else:\n"
        "            out.append(c)\n"
        "    return bytes(out[:total])\n"
        "def safe(body, total):\n"
        "    out = bytearray(); i = 0\n"
        "    while len(out) < total and i < len(body):\n"
        "        c = body[i]; i += 1\n"
        "        if c > 0xC0:\n"
        "            if i >= len(body): break\n"
        "            v = body[i]; i += 1\n"
        "            out += bytes([v]) * (c - 0xC0)\n"
        "        else:\n"
        "            out.append(c)\n"
        "    return bytes(out[:total])\n",
        encoding="utf-8", newline="\n")
    try:
        sample = (lambda: bytes(range(0xB0, 0x100)) * 4)
        frag = ("zz_trunc_probe", "fragile", "刻意脆弱", sample,
                lambda b: ((b, 576), {}), ())
        safe = ("zz_trunc_probe", "safe", "已守衛", sample,
                lambda b: ((b, 576), {}), ())
        r_frag = probe(frag, 60)
        r_safe = probe(safe, 60)
        ok1 = r_frag["verdict"] == "CRASH"
        ok2 = r_safe["verdict"] == "OK"
        print(f"    {'PASS' if ok1 else 'FAIL'}: 脆弱版 -> {r_frag['verdict']} "
              f"({r_frag['detail']})")
        print(f"\n(2) 配對控制:同一段邏輯補上守衛後必須判為 OK")
        print(f"    {'PASS' if ok2 else 'FAIL'}: 已守衛版 -> {r_safe['verdict']} "
              f"({r_safe['detail']})")
        if not ok1:
            fails.append("刻意脆弱的解碼器沒有被抓到 —— 這個檢查是裝飾")
        if not ok2:
            fails.append("已守衛的解碼器被誤判為 CRASH")
    finally:
        probe_mod.unlink(missing_ok=True)
        sys.modules.pop("zz_trunc_probe", None)

    print("\n(3) 合法例外清單要生效,但不能變成萬用赦免")
    e_ok = ("unpack_dat", "parse_directory", "", lambda: b"not a container" * 4,
            lambda b: ((b,), {}), ("NotAContainer",))
    e_bad = ("unpack_dat", "parse_directory", "", lambda: b"not a container" * 4,
             lambda b: ((b,), {}), ())
    r_ok, r_bad = probe(e_ok, 20), probe(e_bad, 20)
    ok3 = r_ok["verdict"] == "OK" and r_bad["verdict"] == "CRASH"
    print(f"    {'PASS' if ok3 else 'FAIL'}: 宣告 NotAContainer -> {r_ok['verdict']};"
          f"不宣告 -> {r_bad['verdict']}(應為 CRASH,證明清單不是無條件放行)")
    if not ok3:
        fails.append("合法例外清單沒有鑑別力")

    print("\n(4) 非空控制:登錄表必須真的跑到資料,不能整排 SKIP")
    rows = [probe(e, 12) for e in DECODERS]
    skipped = [r["tool"] for r in rows if r["verdict"] == "SKIP"]
    ok4 = len(skipped) <= 1
    print(f"    {'PASS' if ok4 else 'FAIL'}: {len(rows)} 個登錄項目,SKIP {skipped or '無'}")
    if not ok4:
        fails.append(f"太多登錄項目找不到取樣資料:{skipped}")

    print("\n(5) 交叉驗證:三支已修好的解碼器,其自己的 selftest 也要通過")
    import subprocess
    agree = []
    for t in ("decode_sprite.py", "decode_lmi.py", "unpack_dat.py"):
        r = subprocess.run([sys.executable, str(Path(__file__).with_name(t)), "--selftest"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=300)
        agree.append((t, r.returncode == 0))
    ok5 = all(v for _t, v in agree)
    print(f"    {'PASS' if ok5 else 'FAIL'}: {agree}")
    if not ok5:
        fails.append(f"兄弟工具的 selftest 不一致:{agree}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(故障注入 + 配對控制 + 例外清單的鑑別力 + "
          "非空控制 + 跨工具交叉驗證)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", type=int, default=120,
                    help="每個解碼器的截斷取樣數與位元翻轉次數(預設 120)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    rows = [probe(e, a.steps, a.seed) for e in DECODERS]
    bad = [r for r in rows if r["verdict"] == "CRASH"]
    for r in rows:
        print(f"  {r['verdict']:<6} {r['tool']:<34} {r['desc']}")
        print(f"         {r['detail']}")
    print(f"\n共 {len(rows)} 個解碼器:安全 {sum(1 for r in rows if r['verdict'] == 'OK')}"
          f" / 崩潰 {len(bad)} / 無取樣資料 {sum(1 for r in rows if r['verdict'] == 'SKIP')}")
    if bad:
        print("**截斷或損壞的輸入會讓這些解碼器丟出非預期例外**:",
              [r["tool"] for r in bad])
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
