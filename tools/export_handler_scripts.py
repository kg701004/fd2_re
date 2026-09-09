#!/usr/bin/env python3
"""Export FD2 EXE cutscene handlers into editable, versioned Handler Script IR.

The EXE remains the evidence source.  This program consumes the deterministic
instruction-level output from dump_chapter_beats.py and emits JSON that is safe
to edit: calls become named operations, while source addresses stay alongside
them for reverse-engineering audit.  Unknown calls are deliberately retained
as ``op: unknown`` rather than silently discarded.

Usage:
  python3 tools/export_handler_scripts.py <FD2.EXE> all <outdir>
  python3 tools/export_handler_scripts.py <FD2.EXE> ch0 <outdir>
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import dump_chapter_beats as raw


SCHEMA_VERSION = 1


def as_int(value):
    """Return an immediate integer, otherwise preserve the original operand."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            pass
    return value


def source_of(beat):
    src = {"addr": beat["addr"]}
    if "target" in beat:
        src["target"] = beat["target"]
    return src


def repeat_of(beat):
    hint = beat.get("repeat_hint")
    if not hint or not isinstance(hint.get("limit"), int):
        return None
    # Handler loops use a zero-based counter compared after the call.  A cmp
    # of N means exactly N calls in the verified chapter-0 loops.
    return hint["limit"]


def normalize(beats, chapter=None):
    """Convert raw disassembly beats to the stable editable IR."""
    out = []
    pending_chapter = None
    pending_chapter_source = None
    for beat in beats:
        op = beat["op"]
        args = [as_int(arg) for arg in beat.get("args", [])]
        src = source_of(beat)
        if op == "loadch_var":
            pending_chapter = as_int(beat["chapter"])
            pending_chapter_source = src
            continue
        if op == "loadch_call":
            item = {"op": "loadch", "source": src}
            if isinstance(pending_chapter, int):
                item["chapter"] = pending_chapter
            else:
                item["chapter_expr"] = pending_chapter
            pending_chapter = None
            pending_chapter_source = None
        elif op == "pan":
            item = {"op": "pan", "grid_x": args[0], "grid_y": args[1], "source": src}
        elif op == "dialog":
            item = {"op": "dialog", "text_index": args[1], "source": src}
            if isinstance(args[0], str):
                item["text_table"] = args[0]
        elif op == "act":
            item = {"op": "act", "acting_id": args[0], "source": src}
        elif op == "spawn":
            item = {
                "op": "spawn", "group": args[0],
                "raw_placement_gate": beat["raw_placement_gate"], "source": src,
            }
        elif op == "join":
            item = {"op": "join", "char_id": args[0], "source": src}
        elif op == "bgm":
            item = {"op": "bgm", "track": args[0], "loop": args[1], "source": src}
        elif op == "scroll_step":
            # 0x13185 follows the supplied original unit slot while scrolling;
            # its argument is not a compass direction.
            item = {"op": "scroll_step", "unit_slot": args[0], "source": src}
            repeat = repeat_of(beat)
            if repeat is not None:
                item["repeat"] = repeat
        elif op == "palfade":
            item = {"op": "palette_fade", "source": src}
        elif op == "delay":
            item = {"op": "delay", "ms": args[0], "source": src}
        elif op == "deactivate_unit":
            item = {"op": "deactivate_unit", "source": src}
            if isinstance(args[0], int):
                item["unit_slot"] = args[0]
            else:
                item["unit_slot_expr"] = args[0]
        elif op == "spawn_intro":
            item = {
                "op": "spawn_intro", "group": args[0],
                "raw_placement_gate": beat["raw_placement_gate"], "source": src,
            }
        elif op == "layout_units":
            # 0x233c6 reads call-site-specific X/Y/pose arrays through
            # registers. Preserve the native call as a named operation; an
            # address-keyed binding supplies the recovered absolute layout.
            item = {"op": "layout_units", "source": src}
        elif op == "reset_pose":
            item = {"op": "reset_pose", "source": src}
        elif op == "focus_unit":
            item = {"op": "focus_unit", "source": src}
            if isinstance(args[0], int):
                item["unit_slot"] = args[0]
            else:
                item["unit_slot_expr"] = args[0]
        elif op == "sync_party":
            item = {"op": "sync_party", "source": src}
        elif op == "grant_item":
            item = {"op": "grant_item", "item_id": args[0], "source": src}
        elif op == "increment_chapter":
            if isinstance(chapter, int):
                item = {"op": "set_chapter", "chapter": chapter + 1, "source": src}
            else:
                item = {"op": "increment_chapter", "source": src}
        elif op == "if":
            item = {
                "op": "if",
                "condition": beat["condition"],
                "then": normalize(beat.get("then", []), chapter),
                "else": normalize(beat.get("else", []), chapter),
                "source": src,
            }
        elif op == "unknown":
            item = {"op": "unknown", "native_target": beat["target"], "source": src}
            if beat.get("args_are_raw_pushes"):
                # 參數個數未達 CONFIRMED,args 是原封不動的 push 序列(cdecl 由右到左),
                # 不是簽名順序。`raw_args` 這個欄位名只有在這種情況下才是誠實的。
                item["raw_args"] = args
                item["args_are_raw_pushes"] = True
            else:
                # 已依 derive_native_argcounts 推導的參數個數切過並反轉 = 簽名順序。
                # 這一半以前也叫 raw_args,那個標籤是錯的,消費端分不出兩種順序。
                item["args"] = args
        else:
            # Conditions and currently non-runtime operations remain editable
            # named records.  Keeping them prevents a lossy “known only” dump.
            item = {"op": op, "args": args, "source": src}
            # doc 錨定的 op 名稱走這條路。出處與「args 不是簽名順序」這兩個標記
            # 必須跟著過來,否則 IR 這一層就看不出名稱是哪來的、args 能不能照順序讀。
            if beat.get("op_name_source"):
                item["op_name_source"] = beat["op_name_source"]
            if beat.get("args_are_raw_pushes"):
                item["args_are_raw_pushes"] = True
        out.append(item)
    if pending_chapter is not None:
        out.append({"op": "set_chapter", "chapter": pending_chapter,
                    "source": pending_chapter_source})
    return out


def walk_beats(beats):
    """Yield editable beats recursively so diagnostics include branch arms."""
    for beat in beats:
        yield beat
        if beat.get("op") == "if":
            yield from walk_beats(beat.get("then", []))
            yield from walk_beats(beat.get("else", []))


def export_table(cg, fx, entries, tag, outdir):
    unique = sorted({handler for _, handler in entries})
    table = raw.handler_beats(cg, fx, entries, unique, raw.OBJ1_END)
    summary = []
    for chapter, handler in table.items():
        script = {
            "schema_version": SCHEMA_VERSION,
            "chapter": chapter,
            "phase": tag,
            "handler": handler["handler"],
            "beats": normalize(handler["beats"], chapter),
        }
        unknown = sum(1 for beat in walk_beats(script["beats"]) if beat["op"] == "unknown")
        script["diagnostics"] = {"unknown_ops": unknown}
        path = os.path.join(outdir, f"ch{chapter:02d}_{tag}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
            f.write("\n")
        summary.append({"chapter": chapter, "phase": tag, "handler": handler["handler"],
                        "beats": len(script["beats"]), "unknown_ops": unknown})
    return summary


def selftest():
    """轉換層自己的檢查。

    這一層以前沒有 --selftest,所以從來沒被突變測試掃過——而它是把原始 beats 變成
    下游真正消費的 IR 的地方,轉錯了不會有人報錯。每一題都成對:只驗「該出現的有
    出現」,對一個永遠輸出同一種形狀的實作也會通過。
    """
    fails = []

    print("(1) 兩種 unknown 的 args 順序相反,IR 必須分得出來")
    # args_are_raw_pushes 的那一半是 cdecl 由右到左的原始 push;另一半已依推導的
    # 參數個數切過並反轉 = 簽名順序。以前兩者都叫 raw_args,消費端無從分辨。
    raw_kind = {"op": "unknown", "addr": "0x1", "target": "0xaaa",
                "args": [1, 2, 3], "args_are_raw_pushes": True}
    sliced = {"op": "unknown", "addr": "0x2", "target": "0xbbb", "args": [4, 5]}
    a, b = normalize([raw_kind, sliced])
    ok1 = (a.get("raw_args") == [1, 2, 3] and a.get("args_are_raw_pushes") is True
           and "args" not in a
           and b.get("args") == [4, 5] and "raw_args" not in b
           and "args_are_raw_pushes" not in b)
    print(f"    {'PASS' if ok1 else 'FAIL'}: 原始 push -> raw_args={a.get('raw_args')}、"
          f"簽名順序 -> args={b.get('args')}")
    if not ok1:
        fails.append(f"兩種 unknown 沒有分開:{a} / {b}")

    print("\n(2) doc 錨定的名稱出處必須帶過來,且不得順手把 args 當成簽名順序")
    named = {"op": "unit_present", "addr": "0x3", "target": "0x22253",
             "args": [10, 15], "args_are_raw_pushes": True,
             "op_name_source": "doc-anchored"}
    got = normalize([named])[0]
    ok2 = (got["op"] == "unit_present" and got.get("op_name_source") == "doc-anchored"
           and got.get("args_are_raw_pushes") is True
           and got["source"]["target"] == "0x22253")
    print(f"    {'PASS' if ok2 else 'FAIL'}: {got}")
    if not ok2:
        fails.append(f"名稱出處或 args 標記在轉換時遺失:{got}")

    print("\n(3) 負向控制:沒有標記的同一筆,不得被憑空補上標記")
    # 沒有這一題,一個「一律補上 op_name_source / args_are_raw_pushes」的實作
    # 也會通過第 (2) 題。
    plain = dict(named)
    plain.pop("op_name_source")
    plain.pop("args_are_raw_pushes")
    got3 = normalize([plain])[0]
    ok3 = "op_name_source" not in got3 and "args_are_raw_pushes" not in got3
    print(f"    {'PASS' if ok3 else 'FAIL'}: 未標記的輸入 -> {sorted(got3)}")
    if not ok3:
        fails.append(f"轉換層自己補了不存在的標記:{got3}")

    print("\n(4) 已收錄的 op 必須轉成具名欄位,而不是留著位置參數")
    known = normalize([
        {"op": "dialog", "addr": "0x4", "target": "0x15f84",
         "args": ["dword ptr [0x3a79]", 7]},
        {"op": "join", "addr": "0x5", "target": "0x112a5", "args": [12]},
    ])
    ok4 = (known[0].get("text_index") == 7
           and known[0].get("text_table") == "dword ptr [0x3a79]"
           and "args" not in known[0]
           and known[1].get("char_id") == 12 and "args" not in known[1])
    print(f"    {'PASS' if ok4 else 'FAIL'}: dialog -> text_index={known[0].get('text_index')}、"
          f"join -> char_id={known[1].get('char_id')}")
    if not ok4:
        fails.append(f"已收錄 op 沒有轉成具名欄位:{known}")

    print("\n(5) 不認得的 op 必須原樣保留(loss-visible),不能被丟掉")
    kept = normalize([{"op": "not_a_real_op", "addr": "0x6", "args": [1]}])
    ok5 = len(kept) == 1 and kept[0]["op"] == "not_a_real_op" and kept[0]["args"] == [1]
    print(f"    {'PASS' if ok5 else 'FAIL'}: {kept}")
    if not ok5:
        fails.append(f"不認得的 op 被丟掉或改寫:{kept}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(兩種 args 順序的配對控制 + 名稱出處帶過來 + "
          "不得憑空補標記的負向控制 + 具名欄位轉換 + loss-visible 保留)。")
    return 0


def main(argv=None):
    if (argv or sys.argv[1:]) == ["--selftest"]:
        return selftest()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe")
    parser.add_argument("scope", choices=("all", "ch0"))
    parser.add_argument("outdir")
    args = parser.parse_args(argv)

    cg = raw.CG(args.exe)
    fx = raw.fixup_map(cg.d, cg.meta)
    os.makedirs(args.outdir, exist_ok=True)
    pre = raw.resolve_table(fx, raw.TABLE_PRE, raw.N_CHAPTERS)
    post = raw.resolve_table(fx, raw.TABLE_POST, raw.N_CHAPTERS)
    if args.scope == "ch0":
        pre = [entry for entry in pre if entry[0] == 0]
        post = [entry for entry in post if entry[0] == 0]
    summary = export_table(cg, fx, pre, "pre", args.outdir)
    summary.extend(export_table(cg, fx, post, "post", args.outdir))
    with open(os.path.join(args.outdir, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"schema_version": SCHEMA_VERSION, "scripts": summary}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"exported {len(summary)} handler scripts to {args.outdir}")


if __name__ == "__main__":
    sys.exit(main() or 0)
