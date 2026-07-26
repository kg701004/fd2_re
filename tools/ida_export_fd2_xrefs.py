"""Export a small, reproducible IDA cross-reference report for FD2.EXE.

Run this only inside the user-authorized local IDA Docker environment.  The
script exports analysis metadata, never the game binary, its database, or any
license material.  The report is intentionally address-oriented so it can be
cross-checked against tools/disasm_le.py's LE linear addresses.
"""

import json
import os

import ida_auto
import ida_funcs
import ida_name
import ida_segment
import ida_xref
import idaapi
import idc


TARGETS = (
    # Save/load → persistent roster → battle-roster bootstrap.  These retain
    # the two source paths for the map-selector cache without naming +7.
    0x10010,
    0x1088D,
    0x10A77,
    # Spawn constructor / visual-selector boundary.  These stay raw addresses:
    # the report establishes call topology, not a guessed FDFIELD schema.
    0x10B4E,
    0x10C50,
    0x11019,
    0x115B6,
    0x14818,
    0x149F8,
    0x1598A,
    0x1A866,
    0x1B750,
    0x1B83D,
    0x1B8A6,
    0x1C269,
    0x1C75E,
    0x1C8ED,
    0x1CA89,
    0x1CFF0,
    # Shared native palette-fade entry.  Its tail is a separate IDA chunk, so
    # retain the public entry/caller topology instead of calling it vsync.
    0x1F882,
    0x22D1B,
    # Event-state entry #12 writer.  Its dispatch provenance is required
    # before the item-0xd0 branch can become an editable scenario event.
    0x356B7,
    # Post-battle layout primitive.  Retain its exact IDA function boundary
    # and callers while call-site array ABI is audited separately.
    0x233C6,
    # Multi-pass map transition compositor.  This is deliberately separate
    # from acting: its ABI is camera/strip geometry and must not become an
    # actor-animation alias.
    0x24618,
    0x4E040,
    0x4E4A2,
    0x4E4D1,
    0x4E516,
    0x4E555,
)
# Address-only metadata is safe to retain as a reproducible RE artifact.  The
# input binary, IDA database, and license stay outside the repository.
OUT_PATH = "/workspace/docs/data/ida/fd2_xrefs.json"


def func_info(ea):
    fn = ida_funcs.get_func(ea)
    if not fn:
        return None
    return {
        "start": fn.start_ea,
        "end": fn.end_ea,
        "name": ida_name.get_name(fn.start_ea) or None,
    }


def code_xrefs_to(ea):
    result = []
    cur = ida_xref.get_first_cref_to(ea)
    while cur != idc.BADADDR:
        result.append({
            "from": cur,
            "from_function": func_info(cur),
        })
        cur = ida_xref.get_next_cref_to(ea, cur)
    return result


def segment_info(ea):
    seg = ida_segment.getseg(ea)
    if not seg:
        return None
    return {"start": seg.start_ea, "end": seg.end_ea, "name": ida_segment.get_segm_name(seg)}


def main():
    ida_auto.auto_wait()
    report = {
        "imagebase": idaapi.get_imagebase(),
        # Keep the checked-in report reproducible when the disposable analysis
        # directory changes; it must not record a host path.
        "input_file": os.path.basename(idc.get_input_file_path()),
        "targets": [
            {
                "address": ea,
                "function": func_info(ea),
                "segment": segment_info(ea),
                "code_xrefs_to": code_xrefs_to(ea),
            }
            for ea in TARGETS
        ],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
        out.write("\n")
    idc.qexit(0)


if __name__ == "__main__":
    main()
