#!/usr/bin/env python3
"""依場景分段的原版實機軌跡:每段執行過哪些函式入口,以及「名稱 → 場景」抽驗(doc98 續一百)。

一次從開機錄到底的 DOSBox-X LOGC 軌跡(原版 FD2.EXE),在每次切換遊戲場景時記下 LOGCPU.TXT 的位元組位置,
事後依位置切成 `seg_NN_<場景>_segcseip.txt`(每段各自去重)。本工具:

  --export OUT DIR   讀 DIR 底下的分段檔,每段算出「入口位址出現在該段軌跡裡」的函式入口集合,寫成
                     `live_scene_entries.json`(決定性;每段附原檔 sha256)。分段檔必須通過與
                     verify_dead_functions_vs_traces.py 相同的內容核對(fallthrough),否則回 2、不寫檔。
  (無參數)          讀已提交的 `live_scene_entries.json`,印每段「本輪第一次執行」的入口與名稱,並檢查 RULES:
                     名稱所說的場景,必須就是該入口本輪第一次執行的那一段;標為獨占的,其他段都不能出現。
                     有規則不成立回 1。
  --selftest         純函式案例(含反向控制),不讀軌跡。

RULES 的依據是擷取時的操作紀錄(每段做了什麼遊戲操作),不是軌跡本身:例如第 23 章戰場只施放過一次「行動術」
(command_labels.json 的 command 25),所以 command_handler_25 應只出現在那一段。

誠實邊界:
  * 段的邊界是人按鍵前後記下的位置,畫面已切換但還沒記位置的那幾步會算進上一段(本輪載入後直接進出擊選人格,
    sortie_member_select 因此落在 title_load 段 —— 規則照實寫)。
  * 「第一次執行」只在這一輪擷取內比較,不含 live_exec_addresses.json 的其他軌跡。
  * 沒出現在某段 ≠ 該段不可能執行;規則只抽驗,不證明全部名稱。

用法:
    python tools/trace_scene_names.py --export docs/data/live_scene_entries.json .wsl_build/live_s100_segments
    python tools/trace_scene_names.py
    python tools/trace_scene_names.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

EXPORT_JSON = ROOT / "docs" / "data" / "live_scene_entries.json"
INVENTORY_JSON = ROOT / "docs" / "data" / "function_inventory.json"
SEG_RE = re.compile(r"^seg_(\d+)_([a-z0-9_]+)_segcseip\.txt$")
EXPORT_PER_LINE = 8

# (名稱, 預期本輪第一次執行的段, 是否獨占該段, 依據)。依據是續一百的操作紀錄。
RULES: list[tuple[str, str, bool, str]] = [
    ("title_menu_dispatch", "boot", False, "開機後的標題選單"),
    ("sortie_member_select", "title_load", False, "第 23 章載入後直接出現出擊選人格(邊界記在之後)"),
    ("sortie_required_member_check", "sortie", True, "選滿 15 人後按確認"),
    ("field_command_ring", "battle", False, "戰場空地按 Return 叫出指令環(battle2 / quit 也用到)"),
    ("options_ring", "battle", True, "只在 battle 段切過音樂 / 音效 / 動畫 / 訊息開關"),
    ("battle_situation_screen", "battle", False, "系統子選單的戰況資訊"),
    ("rest_hp_recover", "battle", False, "哈諾選休息"),
    ("enemy_phase_dispatch", "battle", False, "END 結束回合後的敵方回合"),
    ("command_handler_25", "battle", True, "唯一施放過的法術是行動術(command 25)"),
    ("save_load_restore", "battle_load", False, "系統子選單的讀取戰況"),
    ("church_menu", "church", True, "只在 church 段進過教會"),
    ("revive_service", "church", True, "教會第 2 項(無人可復活的分支)"),
    ("class_change_service", "church", True, "教會第 3 項"),
    ("class_change_apply", "church", True, "凱麗轉職確認 YES"),
    ("shop_menu", "shop", True, "武器店與道具店都在 shop 段"),
    ("shop_buy", "shop", True, "買皮甲、藥草"),
    ("shop_sell_service", "shop", True, "賣出服務"),
    ("town_equip_service", "shop", True, "裝備服務"),
    ("tavern_menu", "tavern", True, "只在 tavern 段進過酒館"),
    ("AIL_shutdown", "quit", True, "系統子選單 C:> 回 DOS"),
    ("crt_exit_to_dos", "quit", True, "同上"),
    ("crt_run_fini", "quit", True, "同上"),
]


def parse_segment_name(name: str) -> tuple[int, str] | None:
    """`seg_NN_<label>_segcseip.txt` -> (NN, label);不符格式回 None。"""
    m = SEG_RE.match(name)
    return (int(m.group(1)), m.group(2)) if m else None


def first_seen(segs: list[tuple[int, str, set[int]]]) -> dict[str, set[int]]:
    """依段序,每段「本輪第一次執行」的入口(前面任何一段出現過的不算)。"""
    seen: set[int] = set()
    out: dict[str, set[int]] = {}
    for _, label, ents in sorted(segs):
        out[label] = ents - seen
        seen |= ents
    return out


def check_rules(segs: list[tuple[int, str, set[int]]], by_name: dict[str, list[int]],
                rules: list[tuple[str, str, bool, str]]) -> list[tuple[str, bool, str]]:
    """每條規則 -> (標籤, 是否成立, 說明)。名稱查不到或不唯一、預期段不存在,都算不成立。"""
    labels = [lb for _, lb, _ in sorted(segs)]
    per = {lb: ents for _, lb, ents in segs}
    first = first_seen(segs)
    out = []
    for name, want, exclusive, why in rules:
        tag = f"{name} -> {want}{'(獨占)' if exclusive else ''}:{why}"
        addrs = by_name.get(name, [])
        if len(addrs) != 1:
            out.append((tag, False, f"名稱對到 {len(addrs)} 個入口"))
            continue
        if want not in per:
            out.append((tag, False, f"沒有 {want} 這一段"))
            continue
        a = addrs[0]
        got = [lb for lb in labels if a in first[lb]]
        also = [lb for lb in labels if a in per[lb] and lb != want]
        ok = got == [want] and (not exclusive or not also)
        out.append((tag, ok, f"{a:#x} 第一次在 {got or '無'},其他段 {also or '無'}"))
    return out


def export_doc(segs: list[tuple[int, str, str, set[int]]], exe_md5: str) -> str:
    """(段號, 場景, 原檔 sha256, 入口集合) -> json 文字(決定性)。"""
    meta = {
        "what": "原版 FD2.EXE 一次從開機錄到底的 DOSBox-X 軌跡,依場景切段;每段列出入口位址出現在該段軌跡裡的函式入口",
        "generator": "python tools/trace_scene_names.py --export docs/data/live_scene_entries.json .wsl_build/live_s100_segments",
        "exe_md5": exe_md5,
        "segments": len(segs),
        "limits": "段的邊界是按鍵前後記下的位置;只在這一輪內比較先後;軌跡在 .wsl_build,不進版控",
    }
    parts = []
    for idx, label, sha, ents in sorted(segs):
        a = sorted(ents)
        rows = [", ".join(f'"{x:#x}"' for x in a[i:i + EXPORT_PER_LINE]) for i in range(0, len(a), EXPORT_PER_LINE)]
        parts.append(f'  {{"index": {idx}, "label": "{label}", "sha256": "{sha}", "entries": [\n   '
                     + ",\n   ".join(rows) + "\n  ]}")
    head = json.dumps({"_meta": meta}, ensure_ascii=False, indent=1)[:-2]
    return head + ',\n "segments": [\n' + ",\n".join(parts) + "\n ]\n}\n"


def read_export(text: str) -> list[tuple[int, str, set[int]]]:
    """`export_doc` 的反向。段號 / 場景重複、位址未排序或重複就 ValueError。"""
    doc = json.loads(text)
    out, idxs, labels = [], set(), set()
    for s in doc["segments"]:
        idx, label = int(s["index"]), str(s["label"])
        if idx in idxs or label in labels:
            raise ValueError(f"段號或場景重複:{idx} {label}")
        idxs.add(idx)
        labels.add(label)
        a = [int(x, 16) for x in s["entries"]]
        if a != sorted(set(a)):
            raise ValueError(f"{label} 的入口未排序或重複")
        out.append((idx, label, set(a)))
    if len(out) != doc["_meta"]["segments"]:
        raise ValueError("segments 筆數與 _meta 不符")
    return out


def inventory_entries() -> set[int]:
    return {int(e["addr"], 16) for e in json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))["entries"]}


def export(out: Path, segdir: Path) -> int:
    import function_inventory as fi
    import verify_address_claim_coverage as CC
    import verify_dead_functions_vs_traces as V
    files = sorted((p for p in segdir.glob("seg_*_segcseip.txt") if parse_segment_name(p.name)),
                   key=lambda p: parse_segment_name(p.name))
    if not files:
        print(f"{segdir} 底下沒有 seg_NN_<label>_segcseip.txt;沒有寫出 {out}。")
        return 2
    _, _, code, base, _ = CC.load_image()
    insn_at = fi.insn_decoder(code, base)
    if insn_at is None:
        print("需要 capstone 才能核對分段檔內容;沒有寫出。")
        return 2
    entries = inventory_entries()
    segs = []
    for p in files:
        idx, label = parse_segment_name(p.name)
        raw = p.read_bytes()
        live = V.parse_trace(raw.decode("utf-8", errors="replace"))
        ok, n = V.fallthrough_ratio(live, insn_at)
        if not V.content_matches(ok, n):
            print(f"{p.name} 內容與這個 EXE 不符(fallthrough {ok}/{n});沒有寫出。")
            return 2
        segs.append((idx, label, hashlib.sha256(raw).hexdigest(), entries & live))
    if len({s[0] for s in segs}) != len(segs) or len({s[1] for s in segs}) != len(segs):
        print("段號或場景名稱重複;沒有寫出。")
        return 2
    md5 = hashlib.md5(open(CC.EXE, "rb").read()).hexdigest()
    out.write_text(export_doc(segs, md5), encoding="utf-8", newline="\n")
    print(f"wrote {out}: {len(segs)} 段")
    return 0


def report(path: Path = EXPORT_JSON, rules: list[tuple[str, str, bool, str]] = RULES,
           names: dict[int, str] | None = None) -> int:
    """印各段本輪第一次執行的入口並檢查規則;有規則不成立回 1。names 預設為登錄表 + Watcom 名稱。"""
    segs = read_export(path.read_text(encoding="utf-8"))
    if names is None:
        import function_inventory as fi
        names = fi.real_names()
    by_name: dict[str, list[int]] = {}
    for a, n in names.items():
        by_name.setdefault(n, []).append(a)
    first = first_seen(segs)
    union: set[int] = set()
    for idx, label, ents in sorted(segs):
        union |= ents
        print(f"== {idx:02d} {label}: 入口 {len(ents)},本輪第一次 {len(first[label])}")
        for a in sorted(first[label]):
            print(f"   {a:#x} {names.get(a, '?')}")
    print(f"\n本輪執行過的入口合計 {len(union)}")
    res = check_rules(segs, by_name, rules)
    bad = [r for r in res if not r[1]]
    print(f"\n名稱 -> 場景規則:{len(res) - len(bad)} / {len(res)} 成立")
    for tag, ok, detail in res:
        print(f"  {'PASS' if ok else 'FAIL'}: {tag} —— {detail}")
    return 1 if bad else 0


def selftest() -> int:
    fails: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        print(f"    {'PASS' if cond else 'FAIL'}: {label}" + ("" if cond else f"  ({detail})"))
        if not cond:
            fails.append(label)

    print("(1) 分段檔名")
    check("seg_07_battle2_segcseip.txt -> (7, battle2)", parse_segment_name("seg_07_battle2_segcseip.txt") == (7, "battle2"))
    check("非分段檔(去重整輪檔)不收", parse_segment_name("s100_lt2_unique_cseip.txt") is None)
    check("場景名稱含大寫或空白不收", parse_segment_name("seg_01_Bad Name_segcseip.txt") is None)

    print("(2) 本輪第一次執行")
    segs = [(0, "boot", {1, 2}), (1, "church", {2, 3, 4}), (2, "shop", {4, 5}), (3, "quit", {1, 6})]
    fs = first_seen(segs)
    check("依段序扣掉前面出現過的", fs == {"boot": {1, 2}, "church": {3, 4}, "shop": {5}, "quit": {6}}, str(fs))
    check("輸入順序打亂結果相同", first_seen(list(reversed(segs))) == fs)

    print("(3) 規則")
    by = {"a3": [3], "a4": [4], "a5": [5], "dup": [3, 99], "a1": [1]}   # dup 的第一個位址本身會成立

    def one(rule: tuple[str, str, bool, str]) -> bool:
        return check_rules(segs, by, [rule])[0][1]
    check("第一次在預期段、獨占 -> 成立", one(("a3", "church", True, "")))
    check("反向:第一次在預期段但別段也有、標獨占 -> 不成立", not one(("a4", "church", True, "")))
    check("同上不標獨占 -> 成立", one(("a4", "church", False, "")))
    check("反向:第一次在別段 -> 不成立", not one(("a5", "church", False, "")))
    check("反向:之後的段又出現不改變第一次(a1 第一次在 boot)", not one(("a1", "quit", False, "")))
    check("反向:名稱對到兩個入口 -> 不成立", not one(("dup", "church", False, "")))
    check("反向:名稱查不到 -> 不成立", not one(("nope", "boot", False, "")))
    check("反向:沒有這一段 -> 不成立", not one(("a3", "tavern", False, "")))

    print("(4) 匯出 / 讀回")
    rows = [(1, "church", "ab" * 32, {0x29daa, 0x2a43e}), (0, "boot", "cd" * 32, set(range(0x10010, 0x10010 + 20)))]
    txt = export_doc(rows, "0" * 32)
    back = read_export(txt)
    check("讀回與匯出相同(段號、場景、入口)", sorted(back) == sorted((i, lb, e) for i, lb, _, e in rows))
    check("匯出是決定性的(輸入順序不影響)", export_doc(list(reversed(rows)), "0" * 32) == txt)
    check("每行 8 個位址", '"0x10010", "0x10011", "0x10012", "0x10013", "0x10014", "0x10015", "0x10016", "0x10017",' in txt)

    def rejects(t: str) -> bool:
        try:
            read_export(t)
        except (ValueError, KeyError, json.JSONDecodeError):
            return True
        return False
    check("反向:場景重複讀不進來", rejects(export_doc([(0, "x", "", {1}), (1, "x", "", {2})], "")))
    check("反向:筆數與 _meta 不符讀不進來", rejects(txt.replace('"segments": 2', '"segments": 3')))
    check("反向:位址未排序讀不進來", rejects(txt.replace('"0x29daa", "0x2a43e"', '"0x2a43e", "0x29daa"')))

    print("(5) 結論層:report 的回傳碼")
    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "scene.json"
        p.write_text(export_doc([(i, lb, "", e) for i, lb, e in segs], ""), encoding="utf-8")
        nm = {3: "a3", 5: "a5"}
        with contextlib.redirect_stdout(io.StringIO()):
            good = report(p, [("a3", "church", True, "")], nm)
            bad = report(p, [("a3", "church", True, ""), ("a5", "church", False, "")], nm)
        check("規則全部成立 -> 回 0", good == 0, str(good))
        check("反向:有一條不成立 -> 回 1", bad == 1, str(bad))

    print("(6) 規則表本身")
    check("規則名稱不重複", len({r[0] for r in RULES}) == len(RULES))
    check("每條規則都有依據", all(r[3] for r in RULES))
    if fails:
        print(f"\n--selftest FAILED: {len(fails)} 項")
        return 1
    print("\n--selftest passed")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", nargs=2, metavar=("OUT", "SEGDIR"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.export:
        return export(Path(a.export[0]), Path(a.export[1]))
    return report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
