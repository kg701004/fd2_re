#!/usr/bin/env python3
"""以原版實機執行軌跡反驗靜態的「死函式」判定(doc98 續九十六)。

輸入是 `tools/dosbox_exec_trace.sh dedup` 產生的去重 CS:EIP 清單(`*unique_cseip.txt`)。
採用哪些由內容決定(`fallthrough_ratio`:非轉移指令的下一條也必須在軌跡裡,別版 EXE 的軌跡過不了);
旁邊有 `FD2.EXE` 的另外要求 md5 與靜態分析的 EXE 相同。檔案份數不等於執行次數 —— 續九十七發現
WSL `~/fd2-run*` 的 251 份是同一份軌跡被 harness 目錄複製,`--export` 以 sha256 去重記錄。
主程式段 CS 0170 的 EIP 減 0x19c000 換成 native 位址(doc48 / doc58 的慣例)。

能被推翻的主張只有一種:靜態判為「沒有執行路徑」的入口(`function_inventory.json` 的 weak 入口、
`function_names.json` 摘要寫「死函式」的入口)的本體,實機不該執行到。
「每個執行位址都落在某個入口的 span 內」必然成立(span 延伸到下一個入口),不拿來當證據。

軌跡本身在 WSL 的 `~/fd2-run*`,不在倉庫裡。`--export` 把採用的軌跡合併成 obj1 內的不重複執行位址,
寫成 `docs/data/live_exec_addresses.json`(只有位址、EXE md5 與每份軌跡檔的 sha256,沒有遊戲資料),
讓 `function_inventory.py --selftest` 每次都能做這項反驗、`--card` 能標出入口有沒有實機執行過(續九十七)。

用法:
    python tools/verify_dead_functions_vs_traces.py TRACE_ROOT [TRACE_ROOT ...]
        TRACE_ROOT 底下遞迴找 trace_unique_cseip.txt(例:WSL 的 ~ 或匯出的資料夾)。
    python tools/verify_dead_functions_vs_traces.py --export docs/data/live_exec_addresses.json TRACE_ROOT ...
    python tools/verify_dead_functions_vs_traces.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME_CS = "0170"
DELTA = 0x19C000
OBJ1 = (0x10000, 0x4EF29)


def parse_trace(text: str, cs: str = GAME_CS, delta: int = DELTA) -> set[int]:
    """`CCCC:IIIIIIII` 每行一筆 -> 指定段的 native 位址集合;格式不對的行略過。"""
    out: set[int] = set()
    for ln in text.splitlines():
        seg, sep, ip = ln.strip().partition(":")
        if not sep or seg.upper() != cs:
            continue
        try:
            out.add(int(ip, 16) - delta)
        except ValueError:
            continue
    return out


def body_hits(starts_spans: dict[int, int], live_sorted: list[int]) -> dict[int, list[int]]:
    """{入口: span} 中,本體 [入口, 入口 + span) 內有實機位址的 -> {入口: 命中位址(排序)}。"""
    hits: dict[int, list[int]] = {}
    for a, span in starts_spans.items():
        i = bisect.bisect_left(live_sorted, a)
        j = bisect.bisect_left(live_sorted, a + span)
        if i < j:
            hits[a] = live_sorted[i:j]
    return hits


TRANSFER = ("j", "call", "ret", "int", "iret", "hlt", "loop")
FALLTHROUGH_MIN_PCT = 99    # 內容相符的門檻:實測相符的 4 份全是 100%,位移 1 或 0x356 的對照組約 26%
FALLTHROUGH_MIN_N = 200     # 太短的軌跡不足以判斷,不採用


def fallthrough_ratio(live: set[int], insn_at) -> tuple[int, int]:
    """(下一條也在軌跡裡的, 檢查的非轉移指令數),只看 obj1 內。

    軌跡屬於這個 EXE 時,非轉移指令執行完一定接著執行 a + 長度;換成別版或位址算錯,
    解碼的指令邊界對不上,比例會掉到三成以下(續九十七實測)。解不出指令的位址算不一致。
    """
    ok = n = 0
    for a in live:
        if not (OBJ1[0] <= a < OBJ1[1]):
            continue
        got = insn_at(a)
        if got is None:
            n += 1
            continue
        size, mn, _ = got
        if mn.startswith(TRANSFER):
            continue
        n += 1
        ok += (a + size) in live
    return ok, n


def content_matches(ok: int, n: int) -> bool:
    return n >= FALLTHROUGH_MIN_N and ok * 100 >= FALLTHROUGH_MIN_PCT * n


def load_live(roots: list[Path], want_md5: str, hashes: list[str] | None = None, insn_at=None,
              log: list[str] | None = None) -> tuple[set[int], int, int]:
    """(native 位址集合, 採用份數, 略過份數)。

    找 `*unique_cseip.txt`(`dosbox_exec_trace.sh dedup` 的輸出,過去也有改名成 trace2_ / cg1v_ 的)。
    採用條件:旁邊有 `FD2.EXE` 時 md5 必須相同;給了 `insn_at` 時內容必須通過 `fallthrough_ratio`
    (旁邊沒有 EXE 的軌跡只能靠這一項);沒給 `insn_at` 又沒有旁邊的 EXE,就無從判斷而略過。
    給了 `hashes` 就把每份採用的軌跡檔 sha256 附加進去(`--export` 記來源用);`log` 收每份的判定。
    """
    live: set[int] = set()
    used = skipped = 0
    for root in roots:
        for f in sorted(root.rglob("*unique_cseip.txt")):
            exe = f.parent / "FD2.EXE"
            side = exe.is_file()
            why = None
            if side and hashlib.md5(exe.read_bytes()).hexdigest() != want_md5:
                why = "旁邊的 FD2.EXE md5 不同"
            raw = f.read_bytes()
            got = parse_trace(raw.decode("utf-8", errors="replace"))
            if why is None and insn_at is None and not side:
                why = "旁邊沒有 FD2.EXE 且沒有反組譯器可驗內容"
            if why is None and insn_at is not None:
                ok, n = fallthrough_ratio(got, insn_at)
                if not content_matches(ok, n):
                    why = f"內容與這個 EXE 不符(fallthrough {ok}/{n})"
            if log is not None:
                log.append(f"{'略過' if why else '採用'} {f}" + (f":{why}" if why else ""))
            if why:
                skipped += 1
                continue
            live |= got
            if hashes is not None:
                hashes.append(hashlib.sha256(raw).hexdigest())
            used += 1
    return live, used, skipped


EXPORT_PER_LINE = 8


def export_doc(live: set[int], exe_md5: str, trace_sha256: list[str], skipped: int) -> str:
    """obj1 內的執行位址 -> `live_exec_addresses.json` 的文字(決定性:位址與 sha256 都排序)。"""
    addrs = sorted(a for a in live if OBJ1[0] <= a < OBJ1[1])
    meta = {
        "what": "原版 FD2.EXE 在 DOSBox-X 實機執行過的指令位址(obj1 內、去重、native),由 dosbox_exec_trace.sh 的軌跡合併",
        "generator": "python tools/verify_dead_functions_vs_traces.py --export docs/data/live_exec_addresses.json .wsl_build",
        "exe_md5": exe_md5,
        "cs": GAME_CS,
        "delta": hex(DELTA),
        "obj1": [hex(OBJ1[0]), hex(OBJ1[1])],
        "trace_files_used": len(trace_sha256),
        "traces_distinct": len(set(trace_sha256)),
        "traces_skipped": skipped,
        "trace_sha256": sorted(set(trace_sha256)),
        "address_count": len(addrs),
        "limits": ("只是過去擷取場景的下限:沒出現不代表沒有執行路徑;軌跡在 WSL ~/fd2-run*,不在倉庫,無法由倉庫重生。"
                   "檔案份數 ≠ 執行次數:harness 目錄複製時會連同軌跡檔一起複製,以 traces_distinct 為準"),
    }
    rows = [", ".join(f'"{a:#x}"' for a in addrs[i:i + EXPORT_PER_LINE]) for i in range(0, len(addrs), EXPORT_PER_LINE)]
    head = json.dumps({"_meta": meta}, ensure_ascii=False, indent=1)[:-2]
    return head + ',\n "addresses": [\n  ' + ",\n  ".join(rows) + "\n ]\n}\n"


def read_export(text: str) -> tuple[set[int], dict]:
    """`export_doc` 的反向:(位址集合, _meta)。排序、重複、範圍、筆數有任何不對就 ValueError,不回半套。"""
    doc = json.loads(text)
    meta, raw = doc["_meta"], doc["addresses"]
    addrs = [int(x, 16) for x in raw]
    if addrs != sorted(set(addrs)):
        raise ValueError("addresses 沒有排序或有重複")
    if addrs and not (OBJ1[0] <= addrs[0] and addrs[-1] < OBJ1[1]):
        raise ValueError("addresses 超出 obj1")
    shas = meta.get("trace_sha256", [])
    if len(addrs) != meta.get("address_count") or meta.get("traces_distinct") != len(shas) or shas != sorted(set(shas)):
        raise ValueError("address_count / traces_distinct / trace_sha256 與內容不符")
    return set(addrs), meta


DEAD_MARK = "(死函式:"


def claimed_dead(inv: list[dict], names: dict[str, dict]) -> set[int]:
    """靜態判為沒有執行路徑的入口:weak,或摘要帶「(死函式:」標記。

    不用「摘要含『死函式』」:0x42270(strong)的摘要只是拿死函式來比較形狀(續九十七訂正)。
    """
    return {int(e["addr"], 16) for e in inv
            if e["grade"] == "weak" or DEAD_MARK in names.get(e["addr"], {}).get("summary", "")}


def exe_md5_and_decoder():
    """(靜態分析用的 FD2.EXE md5, insn_at 或 None(沒有 capstone))。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import function_inventory as FI
    import verify_address_claim_coverage as CC
    _, _, code, base, _ = CC.load_image()
    return hashlib.md5(Path(CC.EXE).read_bytes()).hexdigest(), FI.insn_decoder(code, base)


def run(roots: list[Path]) -> int:
    want, insn_at = exe_md5_and_decoder()
    if insn_at is None:
        print("沒有 capstone:只採用旁邊有 md5 相符 FD2.EXE 的軌跡,不驗內容。")
    hashes: list[str] = []
    live, used, skipped = load_live(roots, want, hashes, insn_at)
    if used == 0:
        print(f"找不到 md5 {want} 的軌跡(略過 {skipped} 份);沒有可驗的資料,不是通過。")
        return 2
    live_obj1 = sorted(a for a in live if OBJ1[0] <= a < OBJ1[1])
    inv = json.loads((ROOT / "docs/data/function_inventory.json").read_text(encoding="utf-8"))["entries"]
    names = {n["addr"]: n for n in json.loads((ROOT / "docs/data/function_names.json").read_text(encoding="utf-8"))["names"]}
    span = {int(e["addr"], 16): e["span_upper"] for e in inv}
    weak = {a: s for a, s in span.items() if next(e for e in inv if int(e["addr"], 16) == a)["grade"] == "weak"}
    dead = {a: span[a] for a in claimed_dead(inv, names) if DEAD_MARK in names.get(hex(a), {}).get("summary", "")}
    print(f"軌跡檔 {used} 份、內容不重複 {len(set(hashes))} 份(md5 {want[:8]}…,略過 {skipped} 份);"
          f"obj1 內不重複執行位址 {len(live_obj1)}")
    bad = 0
    for label, group in (("weak 入口", weak), ("摘要寫「死函式」的入口", dead)):
        hits = body_hits(group, live_obj1)
        print(f"{label}:{len(group)} 個,本體(整個 span)有實機位址的 {len(hits)} 個")
        for a, h in sorted(hits.items()):
            print(f"   {a:#x} {names.get(hex(a), {}).get('name', '-')}:{len(h)} 個位址,例 {[hex(x) for x in h[:4]]}")
        bad += len(hits)
    entry_hit = sum(1 for a in span if a in live)
    print(f"入口位址本身出現在軌跡裡:{entry_hit} / {len(span)}(只是過去擷取場景的下限)")
    # 有命中不自動判錯:span 尾端可能是與活路徑共用的片段(0x46915 的 int N 樁表),要人讀命中位址
    return 1 if bad else 0


def selftest() -> int:
    fails: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
        if not ok:
            fails.append(label)

    text = "0170:001AC010\n0170:001AC012\n0070:00001234\nbad line\n0170:zzzz\n0170:001E26CB\n"
    check("parse_trace:只取 0170、減 0x19c000、略過壞行", parse_trace(text), {0x10010, 0x10012, 0x466CB})
    check("parse_trace:換段", parse_trace(text, cs="0070", delta=0), {0x1234})
    live = sorted({0x10010, 0x10012, 0x10100, 0x20000})
    check("body_hits:span 內命中、span 邊界不含終點、沒命中不列",
          body_hits({0x10010: 0x10, 0x100F0: 0x11, 0x1FFF0: 0x10, 0x30000: 0x100}, live),
          {0x10010: [0x10010, 0x10012], 0x100F0: [0x10100]})
    check("body_hits:空軌跡", body_hits({0x10010: 0x10}, []), {})
    # export_doc / read_export:往返相同、obj1 外的位址不寫、決定性;壞檔要被拒絕
    live_x = {0x10010, 0x4EF28, 0x10000, 0x4EF29, 0x0FFFF, 0x20000, 0x20001, 0x20002, 0x20003, 0x20004, 0x20005, 0x20006, 0x20007}
    txt = export_doc(live_x, "m" * 32, ["b" * 64, "a" * 64, "b" * 64], 3)
    try:
        got, meta = read_export(txt)
    except (ValueError, KeyError) as exc:     # export_doc 寫出 read_export 不收的東西 = export 壞了,記 FAIL 不當掉
        got, meta = set(), {}
        check("export:輸出讀得回來", f"{type(exc).__name__}: {exc}", "")
    check("export:往返相同且只留 obj1(含下界、不含上界)", got, live_x - {0x4EF29, 0x0FFFF})
    check("export:檔案份數與不重複份數分開記(複製的軌跡不算新的一次執行)、sha256 去重排序",
          (meta.get("address_count"), meta.get("trace_files_used"), meta.get("traces_distinct"),
           (meta.get("trace_sha256") or ["?"])[0][0], meta.get("traces_skipped")),
          (11, 3, 2, "a", 3))
    check("export:決定性(輸入順序不同,輸出逐字相同)",
          export_doc(set(sorted(live_x, reverse=True)), "m" * 32, ["b" * 64, "b" * 64, "a" * 64], 3), txt)

    def rejects(t: str) -> bool:
        try:
            read_export(t)
        except (ValueError, KeyError):
            return True
        return False

    check("read_export:筆數不符要拒絕", rejects(txt.replace('"address_count": 11', '"address_count": 12')), True)
    check("read_export:亂序要拒絕", rejects(txt.replace('"0x10000", "0x10010"', '"0x10010", "0x10000"')), True)
    check("read_export:obj1 外要拒絕", rejects(txt.replace('"0x10000"', '"0xffff"')), True)
    check("read_export:traces_distinct 與 sha256 筆數不符要拒絕", rejects(txt.replace('"traces_distinct": 2', '"traces_distinct": 3')), True)
    check("read_export:sha256 重複要拒絕", rejects(txt.replace('"b' + "b" * 63 + '"', '"a' + "a" * 63 + '"')), True)
    inv_x = [{"addr": "0x10", "grade": "weak"}, {"addr": "0x20", "grade": "strong"}, {"addr": "0x30", "grade": "strong"}]
    nm_x = {"0x20": {"summary": "x(死函式:沒有呼叫端)"}, "0x30": {"summary": "與死函式 y 同形"}}
    check("claimed_dead:weak 與「(死函式:」標記;只提到死函式不算", claimed_dead(inv_x, nm_x), {0x10, 0x20})

    # fallthrough_ratio:假解碼器 = 每個位址都是 1 byte 的 nop(0x20000 是 jmp、0x20100 解不出來)
    def fake_insn(a: int):
        return None if a == 0x20100 else ((2, "jmp", "0x0") if a == 0x20000 else (1, "nop", ""))

    check("fallthrough_ratio:連續位址只差最後一條、轉移指令不算、obj1 外不算、解不出來算不一致",
          fallthrough_ratio(set(range(0x20000, 0x20010)) | {0x20100, 0x5}, fake_insn), (14, 16))
    check("content_matches:門檻 99% 與最少 200 條", (content_matches(198, 200), content_matches(197, 200), content_matches(199, 199)),
          (True, False, False))

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)

        def put(sub: str, name: str, addrs, exe: bytes | None) -> None:
            (t / sub).mkdir()
            (t / sub / name).write_text("".join(f"{GAME_CS}:{a + DELTA:08X}\n" for a in addrs), encoding="utf-8")
            if exe is not None:
                (t / sub / "FD2.EXE").write_bytes(exe)

        want = hashlib.md5(b"good").hexdigest()
        put("a_side_ok", "trace_unique_cseip.txt", range(0x30000, 0x30300), b"good")
        put("b_side_bad", "trace_unique_cseip.txt", range(0x31000, 0x31300), b"other")
        put("c_noside", "trace2_unique_cseip.txt", range(0x32000, 0x32300), None)
        put("d_noside_wrong", "cg1v_trace_unique_cseip.txt", range(0x33000, 0x33600, 2), None)
        put("e_noside_short", "x_unique_cseip.txt", range(0x34000, 0x34064), None)
        put("f_side_ok_wrong", "trace_unique_cseip.txt", range(0x35000, 0x35600, 2), b"good")
        live_n, used_n, skip_n = load_live([t], want)
        check("load_live 沒有解碼器:只採用旁邊 md5 相符的(含內容不符的 f,無從判斷)",
              (used_n, skip_n, min(live_n), max(live_n)), (2, 4, 0x30000, 0x355FE))
        log_x: list[str] = []
        live_y, used_y, skip_y = load_live([t], want, [], fake_insn, log_x)
        check("load_live 有解碼器:a 與 c 採用;b(md5)、d(內容)、e(太短)、f(md5 對但內容不符)略過",
              (used_y, skip_y, sorted({a & ~0xFFF for a in live_y})), (2, 4, [0x30000, 0x32000]))
        check("load_live 的判定紀錄每份一行、略過附理由(採用的只到檔名)",
              (len(log_x), sum(x.startswith("略過") and not x.endswith(".txt") for x in log_x),
               sum(x.startswith("採用") and x.endswith(".txt") for x in log_x)), (6, 4, 2))
    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        return 1
    print("\n--selftest passed(18 項純函式與暫存目錄案例)。")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="以原版實機執行軌跡反驗靜態的死函式判定")
    ap.add_argument("roots", nargs="*", type=Path, help="遞迴找 trace_unique_cseip.txt 的根目錄")
    ap.add_argument("--export", metavar="OUT", type=Path, help="把採用的軌跡寫成 live_exec_addresses.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.roots:
        ap.error("需要至少一個 TRACE_ROOT")
    if a.export:
        return export(a.roots, a.export)
    return run(a.roots)


def export(roots: list[Path], out: Path) -> int:
    """合併採用的軌跡寫到 out;要求內容檢查(需要 capstone),沒有任何一份採用就不寫(回 2),不留空檔。"""
    want, insn_at = exe_md5_and_decoder()
    if insn_at is None:
        print("沒有 capstone,無法驗軌跡內容;不匯出。")
        return 2
    hashes: list[str] = []
    log: list[str] = []
    live, used, skipped = load_live(roots, want, hashes, insn_at, log)
    print("\n".join(log))
    if used == 0:
        print(f"找不到 md5 {want} 的軌跡(略過 {skipped} 份);沒有寫出 {out}。")
        return 2
    out.write_text(export_doc(live, want, hashes, skipped), encoding="utf-8", newline="\n")
    _, meta = read_export(out.read_text(encoding="utf-8"))
    print(f"wrote {out}: 軌跡檔 {used} 份、內容不重複 {meta['traces_distinct']} 份(略過 {skipped}),"
          f"obj1 內執行位址 {meta['address_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
