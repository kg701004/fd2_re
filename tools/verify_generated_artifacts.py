#!/usr/bin/env python3
"""fd2_re - re-run each generator and prove its committed output still reproduces.

Why this exists
---------------
2026-09-08, measured: of 99 tools in `tools/`, only 38 have a `--selftest` or are
covered by a `test_*.py`. For the other **61 the repo-wide audit proves only that
they run** -- syntax parses, imports resolve, no crash on startup. Nothing checks
that what they emit is still correct.

For the subset that emits a *committed* artifact there is a cheap, strong check
that needs no new test fixtures: **run the generator again and diff**. It caught a
real drift the day it was first tried by hand -- `docs/data/story_script.json` had
been generated before `decode_story_text.py`'s `PORT` table was corrected against
the game's own name table, so the committed file still said 賽可邦勒 where the
tool now says 塞可邦勒 (90 bytes across three names).

What a result means
-------------------
* `IDENTICAL` -- the committed file is exactly what the current tool produces.
* `DRIFT` -- it is not. Either the tool changed and the artifact was never
  regenerated, or the artifact was hand-edited. **Both need a human**; this tool
  never rewrites a committed file.
* `ERROR` -- the generator could not run (missing input, wrong interpreter…).
  Reported, not hidden: a generator that cannot run is a worse problem than drift.

Honest limits
-------------
* The registry is **curated**, not discovered. 125 of the 135 JSON files under
  `docs/data` do not name the tool that made them, so they cannot be matched
  automatically. Entries here were each confirmed by hand.
* `IDENTICAL` proves *reproducibility*, not *correctness*. If the tool has always
  been wrong, its output reproduces wrongly. This complements the selftest layer,
  it does not replace it.

Usage
-----
    python tools/verify_generated_artifacts.py
    python tools/verify_generated_artifacts.py --only story_script
    python tools/verify_generated_artifacts.py --selftest
"""

from __future__ import annotations

import argparse
import ast
import functools
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EXE = "org_game/炎龍騎士團/FLAME2/FD2.EXE"
FDTXT = "extracted/raw/FDTXT"
RAW = "extracted/raw"
FDFIELD = "org_game/炎龍騎士團/FLAME2/FDFIELD.DAT"

# (artifact, tool, argv template, mode). "{out}" is replaced by a temp path.
#
# `mode` exists because a byte-diff is the wrong question for two real artifacts
# in this repo, and pretending otherwise produced two false DRIFT reports on the
# first run:
#   "bytes"      exact equality (the default, and the strongest).
#   "gen_keys"   only the TOP-LEVEL KEYS the generator emitted must match; keys
#                present solely in the committed file are human enrichment and
#                are listed, not failed. `item_sfx_tables.json` is this shape --
#                its `tables` block reproduces byte-identically while
#                `per_type_lookup` needs an input file no longer in the repo and
#                `_remaining_callers_dataflow_*` is hand-written analysis.
#   "overrides"  like gen_keys, but the committed file carries a
#                `manual_overrides` map and the entries it names are ALLOWED to
#                differ -- and *nothing else may*. That is strictly stronger than
#                skipping the file: it re-proves each round that the documented
#                overrides are still the only deviation. `command_labels.json`
#                has exactly two (ids 9 and 27, each with a written reason).
# Every entry was confirmed by hand -- see the docstring on why this is curated.
REGISTRY: list[tuple[str, str, list[str], str]] = [
    ("docs/data/event_id_groups.json", "extract_event_id_groups.py", ["{out}"], "bytes"),
    ("docs/data/story_script.json", "decode_story_text.py",
     ["--script-json", FDTXT, "{out}"], "bytes"),
    ("docs/data/command_labels.json", "export_command_labels.py",
     [f"{FDTXT}/FDTXT_000.bin", "{out}"], "overrides"),
    ("docs/data/item_labels.json", "export_item_labels.py",
     [f"{FDTXT}/FDTXT_000.bin", "{out}"], "bytes"),
    # 原本照 docstring 用 `--types-json docs/data/item_sfx_dispatch_types.json`,
    # 但那個輸入檔**不在 repo 裡**——工具的用法行本身已過期(同日一併修正)。
    ("docs/data/item_sfx_tables.json", "dump_item_sfx_tables.py",
     ["--output", "{out}"], "gen_keys"),
    ("docs/data/sfx_static_reachability.json", "fd2_sfx_static_reachability.py",
     ["--json", "{out}"], "bytes"),
    ("docs/data/exe_tables", "dump_exe_tables.py", [EXE, "{out}"], "dir"),
    # 2026-09-08 新增。加進來的第一次執行就抓到真東西:treasure 那支把一個
    # **已經是新版位址**的常數又加了一次版本位移(+0x356),輸出 `0x35baa`——
    # 落在指令中段,根本不是函式。已改成從事件跳表 0x51b91 讀(且走 fixup),
    # 並加上序頭檢查與 --selftest。field 那支一次就逐位元組相同。
    ("docs/data/native_field_event_rules.json",
     "extract_native_field_event_rules.py", [EXE, "{out}"], "bytes"),
    ("docs/data/native_treasure_event_rules.json",
     "extract_native_treasure_event_rules.py", [EXE, "{out}"], "bytes"),
    # 2026-09-08 第二批。這三個是 exe_tables/ 目錄項目與 fdfield 那支「不是
    # dump_exe_tables.py 產出」的那幾個檔——原本落在登錄表的視線外。
    # native_unit_tables.json 當時只差 source_size/md5/sha256 三個欄位(記的是
    # 已遺失的舊版 EXE),**所有表格資料逐位元組相同**,即單位表跨版本沒有變動;
    # 本輪重生把來源更正成實際存在的那一版。
    ("docs/data/exe_tables/native_unit_tables.json",
     "extract_native_unit_tables.py", [EXE, "{out}"], "bytes"),
    ("docs/data/exe_tables/terrain.json",
     "dump_terrain_table.py", [RAW, "{out}"], "bytes"),
    # --source 不給就寫成 null;省掉它會產生一個「只有 provenance 不同」的假漂移。
    ("docs/data/fdfield_native_ai_modes.json", "dump_native_ai_modes.py",
     ["--source", FDFIELD, RAW, "{out}"], "bytes"),
    # 2026-09-09:這個產生器一直都在,只是沒人登錄——`encode_text.py revtable`
    # 把 glyph_map.json 反轉成 Unicode->glyph(重複字取最小索引),規則就寫在
    # 產物自己的 `_comment` 裡。它先前被歸進「尚待處理」的 70 個之一,而實測
    # 逐位元組相同(19064 bytes)。發現過程見同輪的 discover() 誤判修正:
    # 舊判準把它的**讀取者** encode_text 認成 glyph_map.json 的產生器,卻反而
    # 沒讓人注意到它真的是 unicode_to_glyph.json 的產生器。
    ("docs/data/unicode_to_glyph.json", "encode_text.py",
     ["revtable", "{out}"], "bytes"),
    # 2026-09-09:27 個未收錄原語的參數個數(呼叫端清理 + 緊鄰 push 兩個獨立訊號,
    # 再與 15 個文件簽名核對)。dump_chapter_beats 用它決定 unknown beat 的 args
    # 要切幾個、要不要反轉,所以這份證據不該只活在記憶體裡——登錄進來,每輪重生
    # 比對,判準一改就會立刻看得出來。
    ("docs/data/native_argcounts.json", "derive_native_argcounts.py",
     ["--wide", "--json", "{out}"], "bytes"),
    # 2026-09-09:61 個 chapter_beats。它們是 hygiene 基準線裡最後一批「實際待處理」,
    # 而擋住登錄的一直是「已提交檔是舊版產出、事後人工補過 op 名」。逐檔比對後,
    # 人工補充只剩兩類且都已處理:12 條註記移到 chapter_beats_notes.json 由匯出時
    # 貼回(貼不上就丟錯),唯一手工結構化的 ch06_post.json 移到 chapter_beats_manual/
    # (它的外層 `if native_event_state_eq` 沒有任何抽取器產得出來)。留一個產不出來
    # 的檔在目錄裡,登錄項目會永遠報漂移——所以先把它移出去,再讓整個目錄可比對。
    # 2026-09-11:worklist 1354 的欄位配置,由 0x4e8bc 消費端掃描 + 跨產物全列對映導出。
    ("docs/data/item_row_field_consumers.json", "derive_item_row_fields.py",
     ["--json", "{out}"], "bytes"),
    # 2026-09-11:Miles AIL 105 個 API 進入點,名字直接取自 binary 自帶的
    # AIL_DEBUG 追蹤字串(是資料,不是推論);見 doc36。
    ("docs/data/ail_entry_points.json", "derive_ail_entry_points.py",
     ["--exe", EXE, "--json", "{out}"], "bytes"),
    # 2026-09-11:事件跳表 58..89 的逐格入口判定,推翻 doc25 的「14 個 table artifact」。
    ("docs/data/event_dispatch_table_58_89.json", "verify_event_dispatch_table.py",
     ["--exe", EXE, "--json", "{out}"], "bytes"),
    ("docs/data/chapter_beats", "dump_chapter_beats.py", [EXE, "all", "{out}"], "dir"),
]

# 已登錄目錄裡**不是該產生器產出**的檔案。
#
# 2026-09-09 發現的漏洞:`coverage()` 對 `dir` 項目是 rglob 整個目錄,所以目錄裡的
# 每個 .json 都拿到「已登錄」身分;但逐位元組比對只比對產生器**實際產出**的那些。
# 兩者的差集因此既不會被比對、也不會出現在待處理清單裡——完全隱形。實測
# `docs/data/exe_tables/` 有 7 個這種檔,其中 5 個既沒有各自的登錄項目、也沒有
# 無產生器證明。`characters.json` 就在裡面,而本 session 稍早正是在它裡面抓到
# 三個錯的角色名。這與「乾淨的總計藏起缺席的列」是同一個模式。
#
# 處理方式不是放寬,而是把差集**明列出來並附理由**,再由 selftest 兩邊夾:
# 實際的差集不能有沒列到的,列到的也必須真的沒有產生器(`discover()` 每次實掃)。
DIR_ORPHANS: dict[str, str] = {
    # 各自有獨立登錄項目(產生器不同,不是 dump_exe_tables.py 產的)。
    "docs/data/exe_tables/native_unit_tables.json": "另有獨立登錄項目",
    "docs/data/exe_tables/terrain.json": "另有獨立登錄項目",
    # 人工記錄的 RE 結果,沒有產生器。`characters.json` 的三個角色名 2026-09-09
    # 依 fdtxt000_name_table.json 更正過,更正方式是直接改檔,不存在重生這條路。
    "docs/data/exe_tables/characters.json": "人工 RE 記錄,無產生器",
    "docs/data/exe_tables/class_change_stat_bonuses.json": "人工 RE 記錄,無產生器",
    "docs/data/exe_tables/class_change_targets.json": "人工 RE 記錄,無產生器",
    "docs/data/exe_tables/revival_cost_coefficients.json": "人工 RE 記錄,無產生器",
    "docs/data/exe_tables/revive_fee_rates.json": "人工 RE 記錄,無產生器",
}


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot() -> dict[str, str]:
    """Hash every committed artifact in the registry, so the run can prove it did
    not touch any of them. A verifier that silently rewrites what it verifies is
    worse than no verifier."""
    out = {}
    for art, _, _, kind in REGISTRY:
        p = ROOT / art
        if kind != "dir" and p.exists():
            out[art] = _hash(p)
        elif kind == "dir" and p.is_dir():
            for f in sorted(p.glob("*.json")):
                out[f"{art}/{f.name}"] = _hash(f)
    return out


def _compare_curated(art: str, tool: str, committed: Path, regen: Path, kind: str) -> dict:
    """Compare a committed artifact that is generator output PLUS human curation.

    Rule for both modes: **every top-level key the generator emitted must match.**
    Keys only in the committed file are enrichment and are reported, not failed.
    In `overrides` mode the committed file additionally names entries that are
    permitted to differ, and the check asserts those are the ONLY differences --
    so a real regression inside a curated file still shows up.
    """
    import json
    try:
        c = json.loads(committed.read_text(encoding="utf-8"))
        g = json.loads(regen.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"artifact": art, "tool": tool, "verdict": "ERROR",
                "detail": f"JSON 解析失敗: {exc}"[:120]}
    if not isinstance(c, dict) or not isinstance(g, dict):
        return {"artifact": art, "tool": tool, "verdict": "ERROR",
                "detail": "curated 模式只支援頂層 dict"}

    overrides = c.get("manual_overrides") or {}
    allowed = {str(k) for k in overrides} if kind == "overrides" else set()
    bad, extra = [], sorted(set(c) - set(g))
    for k in g:
        if k not in c:
            bad.append(f"+{k}(重生有、committed 無)")
        elif c[k] == g[k]:
            continue
        elif kind == "overrides" and isinstance(c[k], list) and isinstance(g[k], list) \
                and len(c[k]) == len(g[k]):
            # 逐項比對:只有被 manual_overrides 指名的項目可以不同。
            for i, (x, y) in enumerate(zip(c[k], g[k])):
                if x == y:
                    continue
                ident = str(x.get("command_id", i)) if isinstance(x, dict) else str(i)
                if ident not in allowed:
                    bad.append(f"{k}[{ident}]")
        else:
            bad.append(k)
    return {"artifact": art, "tool": tool,
            "verdict": "IDENTICAL" if not bad else "DRIFT",
            "curated_keys": extra, "allowed_overrides": sorted(allowed),
            "unexpected": bad[:6]}


def check_one(art: str, tool: str, argv: list[str], kind: str, timeout: int) -> dict:
    p = ROOT / art
    if not p.exists():
        return {"artifact": art, "tool": tool, "verdict": "MISSING_ARTIFACT"}
    with tempfile.TemporaryDirectory(prefix="regen_") as td:
        out = Path(td) / ("regen.json" if kind == "file" else "regen_dir")
        real = [a.replace("{out}", str(out)) for a in argv]
        # 2026-09-11:突變測試把 `text=True` 改成 `False` 逃掉了 —— 查過是可證明的
        # 等價突變(不是取樣沒打到):Python 文件明記 subprocess.run 只要給了
        # `encoding=`(這裡固定給),就會強制文字模式,`text=`/`universal_newlines=`
        # 的值本身不再有作用(實測 `text=False, encoding="utf-8"` 仍回傳 str)。
        # 這裡刻意兩個都寫,是給讀者看意圖;`capture_output=` 才是真的承重的旗標,
        # 已由 (4c) 題(強迫走錯誤路徑,對照 r.stdout/r.stderr 有沒有被真的捕捉)釘住。
        r = subprocess.run([sys.executable, str(ROOT / "tools" / tool), *real],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=timeout)
        if kind != "dir":
            if not out.exists():
                tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
                return {"artifact": art, "tool": tool, "verdict": "ERROR",
                        "detail": (tail[-1][:120] if tail else f"rc={r.returncode}")}
            if kind == "bytes":
                same = p.read_bytes() == out.read_bytes()
                return {"artifact": art, "tool": tool,
                        "verdict": "IDENTICAL" if same else "DRIFT",
                        "sizes": None if same else [p.stat().st_size, out.stat().st_size]}
            return _compare_curated(art, tool, p, out, kind)
        # directory: compare only the files the generator actually produced
        if not out.is_dir():
            tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            return {"artifact": art, "tool": tool, "verdict": "ERROR",
                    "detail": (tail[-1][:120] if tail else f"rc={r.returncode}")}
        made = sorted(f.name for f in out.glob("*.json"))
        drift = [n for n in made
                 if not (p / n).exists() or (p / n).read_bytes() != (out / n).read_bytes()]
        return {"artifact": art, "tool": tool,
                "verdict": "IDENTICAL" if not drift else "DRIFT",
                "produced": len(made), "drifted": drift[:6],
                "not_from_this_tool": len([f for f in p.glob('*.json')]) - len(made)}


def selftest() -> int:
    """Controls in both directions, plus proof the comparator is not blind."""
    fails = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        a, b = d / "a.json", d / "b.json"
        a.write_text('{"x": 1}\n', encoding="utf-8")

        print("(1) 負向控制:內容相同必須判為相同")
        shutil.copy(a, b)
        ok1 = a.read_bytes() == b.read_bytes()
        print(f"    {'PASS' if ok1 else 'FAIL'}: {ok1}")
        if not ok1:
            fails.append("相同內容被判為不同")

        print("\n(2) 正向控制:改一個位元組必須判為不同")
        b.write_text('{"x": 2}\n', encoding="utf-8")
        ok2 = a.read_bytes() != b.read_bytes()
        print(f"    {'PASS' if ok2 else 'FAIL'}: {ok2}")
        if not ok2:
            fails.append("被改動的內容仍被判為相同")

        print("\n(3) 大小相同但內容不同也必須抓到(story_script 的真實形狀)")
        # 那次真實漂移就是「同大小、90 個位元組不同」,只比大小會整個漏掉。
        a.write_text('{"n": "賽"}\n', encoding="utf-8")
        b.write_text('{"n": "塞"}\n', encoding="utf-8")
        ok3 = (a.stat().st_size == b.stat().st_size) and (a.read_bytes() != b.read_bytes())
        print(f"    {'PASS' if ok3 else 'FAIL'}: 同大小={a.stat().st_size == b.stat().st_size}, 判為不同={a.read_bytes() != b.read_bytes()}")
        if not ok3:
            fails.append("同大小不同內容沒被抓到")

    print("\n(4) overrides 模式必須只放行被指名的項目 —— 否則放寬等於關掉檢查")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        base = {"entries": [{"command_id": 0, "label": "A"},
                            {"command_id": 9, "label": "人工值"}],
                "manual_overrides": {"9": {"reason": "測試"}}}
        gen = {"entries": [{"command_id": 0, "label": "A"},
                           {"command_id": 9, "label": "原始解碼"}]}
        c, g = d / "c.json", d / "g.json"
        import json as _j
        c.write_text(_j.dumps(base), encoding="utf-8")
        g.write_text(_j.dumps(gen), encoding="utf-8")
        r1 = _compare_curated("t", "t", c, g, "overrides")
        ok4a = r1["verdict"] == "IDENTICAL"
        print(f"    {'PASS' if ok4a else 'FAIL'}: 被指名的覆寫(id 9)不算漂移 -> {r1['verdict']}")
        if not ok4a:
            fails.append(f"合法覆寫被誤判為漂移:{r1}")
        # 正向控制:動一個「沒有被指名」的項目,必須被抓到。
        gen["entries"][0]["label"] = "B"
        g.write_text(_j.dumps(gen), encoding="utf-8")
        r2 = _compare_curated("t", "t", c, g, "overrides")
        ok4b = r2["verdict"] == "DRIFT" and any("0" in x for x in r2["unexpected"])
        print(f"    {'PASS' if ok4b else 'FAIL'}: 未被指名的 id 0 改動必須抓到 -> "
              f"{r2['verdict']} {r2.get('unexpected')}")
        if not ok4b:
            fails.append(f"overrides 模式漏掉未指名的改動:{r2}")

    print("\n(4c) check_one 的錯誤路徑必須真的捕捉到子行程輸出,不能退化成只有 rc")
    # (5) 只在**現有 92 個登錄項目全部成功**的前提下跑 run_all,從沒真的踩過
    # `not out.exists()` 這條錯誤分支 —— subprocess.run 的 capture_output/text
    # 兩個旗標只在這條路徑上才觀察得到差異(成功案例完全不讀 r.stdout/r.stderr)。
    # 直接指一個不存在的工具檔案,強迫 check_one 走錯誤路徑。
    err = check_one("docs/data/known_address_errata.json", "does_not_exist_xyz.py",
                    ["{out}"], "file", 30)
    ok4c = (err["verdict"] == "ERROR"
           and "detail" in err
           and "rc=" not in err["detail"]
           and ("cannot open" in err["detail"].lower() or "can't open" in err["detail"].lower()
                or "no such file" in err["detail"].lower()))
    print(f"    {'PASS' if ok4c else 'FAIL'}: detail={err.get('detail', '')[:70]!r}")
    if not ok4c:
        fails.append(f"check_one 的錯誤路徑沒有捕捉到真正的子行程輸出:{err}")

    print("\n(5) 安全性:實際跑一輪後,所有已提交產物的雜湊必須完全不變")
    before = snapshot()
    run_all(timeout=900, quiet=True)
    after = snapshot()
    changed = [k for k in before if before[k] != after.get(k)]
    print(f"    {'PASS' if not changed else 'FAIL'}: {len(before)} 個產物,變動 {len(changed)} 個"
          + (f" {changed[:4]}" if changed else ""))
    if changed:
        fails.append(f"本工具改動了已提交產物:{changed[:4]}")

    print("\n(6) 涵蓋率報告必須兩邊都對:登錄的不算未涵蓋,未登錄的一定要出現在清單裡")
    total, covered, missing = coverage()
    reg_sample = "docs/data/native_treasure_event_rules.json"      # 直接登錄
    dir_sample = "docs/data/exe_tables/spell.json"                 # 經 dir 模式涵蓋
    ok_a = reg_sample not in missing and dir_sample not in missing
    # 負向:隨便一個沒登錄的產物必須被列出來,否則這個報告只是印個好看的數字
    ok_b = len(missing) > 0 and all((ROOT / m).exists() for m in missing[:20])
    ok_c = total == covered + len(missing)
    print(f"    {'PASS' if ok_a else 'FAIL'}: 已登錄的兩個樣本(含 dir 模式)不在未涵蓋清單")
    print(f"    {'PASS' if ok_b else 'FAIL'}: 未涵蓋清單有 {len(missing)} 項且都是真實存在的檔")
    print(f"    {'PASS' if ok_c else 'FAIL'}: {total} = {covered} + {len(missing)}")
    if not (ok_a and ok_b and ok_c):
        fails.append(f"涵蓋率報告不正確(total={total} covered={covered} missing={len(missing)})")

    print("\n(7) discover() 的判準:對真實原始碼區分「寫入目標」與「離寫入很近」")
    # 五個案例全部來自 repo 裡真的長這樣的程式碼,不是合成的。前四個是舊判準
    # 的三種誤判來源(內容字串 / 別人的引數 / 讀取路徑),第五個是真的產生器
    # ——只有反向不成立才算數:全判 EXCLUDE 也能通過前四題。
    ROLE_CASES = [
        ("decode_story_text.py",     "glyph_map.json",        False),
        ("export_command_labels.py", "glyph_map.json",        False),
        ("export_item_labels.py",    "glyph_map.json",        False),
        ("encode_text.py",           "glyph_map.json",        False),
        ("encode_text.py",           "unicode_to_glyph.json", True),
    ]
    wrong = []
    for tool, base, want in ROLE_CASES:
        p = ROOT / "tools" / tool
        if not p.exists():
            wrong.append(f"{tool} 不存在")
            continue
        got = bool(write_target_lines(p.read_text(encoding="utf-8"), base))
        if got != want:
            wrong.append(f"{tool}/{base}: 得 {got},應 {want}")
    # 非平凡性:這五題必須同時包含正例與反例,否則一個「永遠回 False」的實作
    # 也會全過。
    both = {w for _, _, w in ROLE_CASES} == {True, False}
    ok7 = not wrong and both
    print(f"    {'PASS' if ok7 else 'FAIL'}: 5 個真實案例"
          + ("全部相符,且正反例俱在" if ok7 else f",不符 {wrong}、正反例俱在={both}"))
    if not ok7:
        fails.append(f"discover() 判準不符:{wrong}")

    print("\n(8) 效能回歸防呆:同一份原始碼不論查幾個檔名,只准解析一次")
    # 用解析次數而不是耗時來斷言——耗時會隨機器飄,次數不會。這一題是實際
    # 事故的回歸:判準第一版寫成 f(src, basename),discover() 的 109 個產物 ×
    # 119 支工具各自重新 ast.parse 一次,單次 discover() 32 秒,而
    # _proves_no_generator 每個永久豁免項目呼叫一次(47 項),
    # verify_tool_hygiene 於是在全工具稽核裡 timed out(1220s,平時 320s)。
    src8 = (ROOT / "tools" / "encode_text.py").read_text(encoding="utf-8")
    real_parse, calls = ast.parse, []
    def counting_parse(*a, **k):                                  # noqa: ANN
        calls.append(1)
        return real_parse(*a, **k)
    _write_target_index.cache_clear()
    ast.parse = counting_parse
    try:
        for i in range(60):
            write_target_lines(src8, f"nonexistent_{i}.json")
        write_target_lines(src8, "unicode_to_glyph.json")
    finally:
        ast.parse = real_parse
    ok8 = len(calls) == 1
    print(f"    {'PASS' if ok8 else 'FAIL'}: 61 次查詢共解析 {len(calls)} 次(應為 1)")
    if not ok8:
        fails.append(f"每次查詢都重新解析:{len(calls)} 次")

    print("\n(9) 已登錄目錄裡的每個檔,都必須真的被某個東西涵蓋(兩邊夾)")
    # 漏洞:coverage() 對 dir 項目 rglob 整個目錄,但比對只涵蓋產生器**實際產出**
    # 的檔;差集因此拿到「已登錄」身分卻從未被比對,也不會出現在待處理清單裡。
    orphan_bad = []
    seen_orphans = set()
    for art, tool, argv, kind in REGISTRY:
        if kind != "dir":
            continue
        # 直接跑:實測兩個目錄產生器合計 1.3 秒。先前為此加過跨行程快取,
        # 但量測顯示這支 selftest 的 23.5 秒其實在第 (5) 題(它會實跑一輪完整驗證),
        # 與這裡無關——快取是在解一個不存在的問題,還多一個過期快取的失效面,已撤除。
        with tempfile.TemporaryDirectory(prefix="orphan_") as td:
            out = Path(td) / "regen_dir"
            real = [a.replace("{out}", str(out)) for a in argv]
            subprocess.run([sys.executable, str(ROOT / "tools" / tool), *real],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=600)
            made = {f.name for f in out.glob("*.json")} if out.is_dir() else set()
        for q in sorted((ROOT / art).glob("*.json")):
            rel = f"{art}/{q.name}"
            if q.name in made:
                continue
            seen_orphans.add(rel)
            if rel not in DIR_ORPHANS:
                orphan_bad.append(f"{rel}:在已登錄目錄裡,但不是產生器產出、也沒列進 DIR_ORPHANS")
    # 反向:列進 DIR_ORPHANS 的必須真的是差集(否則清單會腐爛成免死金牌),
    # 而且宣稱「無產生器」的那幾筆,discover() 每次實掃都必須掃不到產生器。
    registered_names = {a for a, _, _, _ in REGISTRY}
    found = dict(discover())
    for rel, why in sorted(DIR_ORPHANS.items()):
        if rel not in seen_orphans:
            orphan_bad.append(f"{rel}:已不在差集裡,請從 DIR_ORPHANS 移除")
        elif "無產生器" in why:
            gen = [t for t, arts in found.items() if rel in arts]
            if gen:
                orphan_bad.append(f"{rel}:宣稱無產生器,但 {gen} 看起來會產生它")
        elif rel not in registered_names:
            orphan_bad.append(f"{rel}:宣稱另有登錄項目,但登錄表裡找不到")
    ok9 = not orphan_bad and len(seen_orphans) >= 5
    print(f"    {'PASS' if ok9 else 'FAIL'}: 差集 {len(seen_orphans)} 個,"
          + ("全部有明列理由且理由成立" if ok9 else f"問題 {orphan_bad[:3]}"))
    if not ok9:
        fails.append(f"已登錄目錄有未涵蓋的檔:{orphan_bad[:3]}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向/負向各 1 + 同大小案例 + overrides 放行與攔截的配對控制 "
          "+ 不改動已提交檔案 + 涵蓋率報告的正反向對照 + discover() 判準的五個真實案例 "
          "+ 效能回歸防呆 + 已登錄目錄差集的兩邊夾)。")
    return 0


def run_all(only: str | None = None, timeout: int = 900, quiet: bool = False) -> list[dict]:
    rows = []
    for art, tool, argv, kind in REGISTRY:
        if only and only not in art and only not in tool:
            continue
        r = check_one(art, tool, argv, kind, timeout)
        rows.append(r)
        if quiet:
            continue
        v = r["verdict"]
        extra = ""
        if v == "DRIFT":
            extra = f" {r.get('unexpected') or r.get('drifted') or r.get('sizes')}"
        elif v == "ERROR":
            extra = f" {r.get('detail','')}"
        elif v == "IDENTICAL" and "produced" in r:
            extra = f" ({r['produced']} 個檔;另有 {r['not_from_this_tool']} 個非此工具產出)"
        elif v == "IDENTICAL" and r.get("curated_keys"):
            extra = (f" (產生器鍵全數一致;人工增補鍵 {r['curated_keys']}"
                     + (f";允許覆寫 {r['allowed_overrides']}" if r.get("allowed_overrides") else "") + ")")
        print(f"  {r['verdict']:<16} {art:<44} <- {tool}{extra}")
    return rows


def coverage() -> tuple[int, int, list[str]]:
    """已提交的 docs/data 產物中,有幾個真的被這張登錄表涵蓋。

    2026-09-08:加這個是因為「共 12 項:相同 12」讀起來像「全部都對」,但它其實
    只說了登錄表裡那幾項——**沒有登錄項目的產物,在這份報告裡完全不存在**,
    而那才是大多數。乾淨的總計會藏起缺席的列,所以把分母印出來。
    """
    registered = set()
    for art, _, _, kind in REGISTRY:
        p = ROOT / art
        if kind == "dir" and p.is_dir():
            registered.update(str(q.relative_to(ROOT)).replace("\\", "/")
                              for q in p.rglob("*.json"))
        else:
            registered.add(art)
    all_art = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                     for p in (ROOT / "docs/data").rglob("*.json"))
    missing = [a for a in all_art if a not in registered]
    return len(all_art), len(all_art) - len(missing), missing


def no_generator_set() -> set[str]:
    """已由 hygiene 棘輪**證明沒有產生器**的產物。

    2026-09-08:分母要一路誠實。「110 個從未被重生比對過」在 40 個已證明沒有
    產生器之後就變成誤導 —— 那 40 個不是「還沒做」,是「這條路不適用」。
    來源是 `docs/data/hygiene_baseline.json` 的 `permanent: no_generator`,
    而那個標記本身由 `verify_tool_hygiene` 第 (3b) 項每次實跑驗證(它會回頭呼叫
    本檔的 `discover()`,只要有人寫了產生器就會失敗)。兩邊互相牽制,不會各自漂移。
    """
    p = ROOT / "docs" / "data" / "hygiene_baseline.json"
    if not p.exists():
        return set()
    try:
        entries = json.loads(p.read_text(encoding="utf-8")).get("entries", [])
    except (OSError, ValueError):
        return set()
    # 2026-09-09:原本只認 `no_generator` 一種,結果本檔說「尚待處理 7 個」而
    # `verify_tool_hygiene` 對**同一批檔案**說「實際待處理 0 筆」——兩支工具對同一個
    # 事實給出不同答案,而它們本來就是設計成互相牽制的。差在後來新增的兩種永久豁免:
    # `lost_input`(產生器還在,但它吃的那份位元組已經不存在)與 `remake_derived`
    # (產生它的 remake 測試已隨目錄移除)。這三種說的都是同一件事——**重生比對這條路
    # 對這個產物不適用**——所以三種都算。`ida_embedded` 不算:那是工具側的規則
    # (correctness),不是產物側的。
    return {e["name"] for e in entries
            if e.get("rule") == "regenerable"
            and e.get("permanent") in {"no_generator", "lost_input", "remake_derived"}}


WRITE_CTX = re.compile(r"json\.dump|write_text\(|\bopen\([^)]*[\"']w[\"btx+]*[\"']"
                       r"|\bout\w*\s*=|\bdst\w*\s*=|--output|--json\b")


_PATH_CTORS = {"Path", "PurePath", "join", "joinpath", "resolve", "expanduser"}
_CONTENT_CALLS = {"write", "writelines", "print"}
_SINK_CALLS = {"open", "write_text", "write_bytes", "dump"}


@functools.lru_cache(maxsize=512)
def _write_target_index(src: str) -> tuple[tuple[int, str], ...]:
    """一份原始碼裡所有「以寫入目標身分出現」的字串字面值 (行號, 值)。

    **與檔名無關,所以整份快取。** 2026-09-09:第一版把角色判定寫成
    `f(src, basename)`,於是 `discover()` 的 109 個產物 × 119 支工具會各自
    重新 `ast.parse` 一次整份原始碼——一萬三千次。單次 `discover()` 因此要
    32 秒,而 `_proves_no_generator` 每個永久豁免項目呼叫一次(47 項),
    `verify_tool_hygiene` 直接在全工具稽核裡 **timed out**(1220s,平時 320s)。
    判準本身是對的,代價下在錯的地方:角色與寫入語境都只跟原始碼有關,
    跟要找哪個檔名無關,所以應該算一次就好。
    """
    role = _path_role_lines(src)
    rows = src.splitlines()
    return tuple((n, v) for n, v in sorted(role)
                 if WRITE_CTX.search("\n".join(rows[max(0, n - 3):n + 2])))


def _path_role_lines(src: str) -> set[tuple[int, str]]:
    """所有以「路徑」身分(而非內容、也非別人的引數)出現的字串字面值。

    從字串字面值往上走,先跳過純粹在組路徑的包裝(`Path(...)`、`os.path.join`、
    `/` 運算),再看**第一個非路徑組裝的節點**決定它的角色:

    - `.write()`/`print()` 的引數 -> 它是被寫出去的**內容**,不是路徑
    - `open`/`write_text`/`json.dump` 的引數 -> 它就是**寫入目標**
    - 指派敘述 -> 這個字面值在為某條路徑命名,是候選
    - 其他任何呼叫的引數 -> 它是**別人的輸入**,不是這支工具的輸出

    三種誤判都出自同一個毛病——「檔名離寫入很近」被當成「檔名是寫入目標」:
      1. `decode_story_text.py:410` `f.write("> 由 FDTXT.DAT + glyph_map.json
         自動解碼...")`,一句寫進 markdown 的出處註記(內容)
      2. `export_command_labels.py:72` `output = export(..., ".../glyph_map.json")`,
         檔名是 `export()` 的讀取輸入,真正的寫入目標是 `Path(argv[2])`;正則
         被同一行的 `output =` 命中
      3. `decode_story_text.py:104` `d = os.path.join(..., "glyph_map.json")`,
         是路徑沒錯,但那是 `json.load` 的讀取路徑——這一種靠下面的 ±2 行
         寫入語境擋掉,兩個條件缺一不可

    已知限制:多行字串只記起始行。
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    found: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        cur = parents.get(node)
        while cur is not None:
            if isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
                cur = parents.get(cur)
                continue
            if isinstance(cur, ast.Call):
                f = cur.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in _PATH_CTORS:
                    cur = parents.get(cur)
                    continue
                if name in _SINK_CALLS:
                    found.add((node.lineno, node.value))
                break
            if isinstance(cur, (ast.Assign, ast.AnnAssign)):
                found.add((node.lineno, node.value))
                break
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                break
            cur = parents.get(cur)
    return found


def write_target_lines(src: str, basename: str) -> list[int]:
    """檔名以**寫入目標**身分出現的行號(1-based)。角色與寫入語境都要成立。"""
    return [n for n, v in _write_target_index(src) if basename in v]


def discover() -> list[tuple[str, list[str]]]:
    """Propose (tool, artifacts) pairs for the uncovered backlog.

    The registry is curated on purpose — a name match is a lead, not proof, and
    every entry here has to be confirmed by an actual regeneration. But going
    through 109 uncovered artifacts by hand needs a starting list, and writing
    that list as a throwaway script is exactly the habit that produced a false
    mismatch earlier today. So it lives here, next to the registry it feeds.

    A tool is proposed only if it *writes* (json.dump / open(...,"w") /
    write_text) and mentions the artifact's basename; readers are excluded,
    which is what separates `char_summary.py` (reads characters.json, emits a
    PNG) from a real generator.
    """
    _, _, missing = coverage()
    by_base: dict[str, list[str]] = {}
    for m in missing:
        by_base.setdefault(Path(m).name, []).append(m)
    # 2026-09-08:第一版只要求「這支工具會寫檔」且「原始碼裡提到這個檔名」,
    # 結果把一堆**讀取者**列成候選(七支工具都提到 glyph_map.json,沒有一支產生它)。
    # 改成要求檔名出現在**寫入語境**:同一行或前後兩行內有寫入呼叫。
    # 2026-09-09:那還是不夠——見 write_target_lines,「離寫入很近」和「是寫入
    # 目標」是兩回事,寫進輸出檔的一句出處註記同時滿足前者。改用兩者的合取。
    out = []
    for tool in sorted((ROOT / "tools").glob("*.py")):
        if tool.name.startswith("test_") or tool.name.startswith("verify_"):
            continue
        src = tool.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"json\.dump|write_text\(|open\([^)]*[\"']w[\"btx+]*[\"']", src):
            continue
        hits = set()
        for base, arts in by_base.items():
            if write_target_lines(src, base):
                hits.update(arts)
        if hits:
            out.append((tool.name, sorted(hits)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true",
                    help="列出未涵蓋產物的候選產生器(是線索,不是證明——每一項仍須實跑確認)")
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--coverage", action="store_true",
                    help="列出所有沒有登錄項目、因此從未被重生比對過的已提交產物")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.discover:
        props = discover()
        print(f"未涵蓋產物的候選產生器 {len(props)} 支"
              f"(**線索,不是證明**——每一項都要實跑重生比對過才可登錄):")
        for tool, arts in props:
            print(f"  {tool}")
            for x in arts:
                print(f"      {x}")
        return 0
    if a.coverage:
        total, covered, missing = coverage()
        nogen = no_generator_set()
        pending = [m for m in missing if m not in nogen]
        print(f"docs/data 已提交 JSON {total} 個:登錄表涵蓋 {covered} 個、"
              f"已證明重生比對不適用 {len(nogen)} 個、**尚待處理 {len(pending)} 個**")
        print("\n尚待處理(有機會登錄,或需要查清楚):")
        for m in pending:
            print("  ", m)
        print("\n已證明重生比對不適用(無產生器/輸入已遺失/remake 產出;"
              "宣稱由 hygiene 第 (3b)(3c)(3d) 項各自驗證):")
        for m in sorted(nogen):
            print("  ", m)
        return 0
    rows = run_all(a.only, a.timeout)
    drift = [r for r in rows if r["verdict"] == "DRIFT"]
    err = [r for r in rows if r["verdict"] == "ERROR"]
    total, covered, missing = coverage()
    print(f"\n共 {len(rows)} 項:相同 {sum(1 for r in rows if r['verdict']=='IDENTICAL')}"
          f" / 漂移 {len(drift)} / 無法執行 {len(err)}")
    # 分母跟著印,否則上面那行讀起來像「全部產物都對」;而未涵蓋的那堆還要再拆一次,
    # 否則「已證明沒有產生器」會被混進「還沒做」裡,讓剩餘量看起來比實際多。
    nogen = no_generator_set()
    pending = [m for m in missing if m not in nogen]
    print(f"涵蓋率:docs/data 的 {total} 個已提交 JSON 中,{covered} 個有登錄項目、"
          f"{len(nogen)} 個**已證明重生比對不適用**(無產生器/輸入已遺失/remake 產出)、"
          f"{len(pending)} 個**尚待處理**(`--coverage` 可列出)")
    if drift:
        print("  **漂移(需人工判斷是工具變了還是產物被手改)**:", [r["artifact"] for r in drift])
    if err:
        print("  **無法執行**:", [(r["artifact"], r.get("detail", "")[:60]) for r in err])
    return 1 if (drift or err) else 0


if __name__ == "__main__":
    raise SystemExit(main())
