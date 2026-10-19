"""續一百二十七:正式第 22 章戰場的戰後處理器紀錄(lc127b r1)與三張表的靜態檢查(原暫存 an127.py,續一百三十四移進倉庫)。
用法:lc127_analyze.py [r1.json] [lc126 r1.json] [cycles 2500 資料夾] [cycles 5000 資料夾];ev_lut_ch22_post_cycles2500_chapter_tables.py 呼叫 main()。

靜態值(戰後表第 22 格、call 長度、push 立即值、章節表呼叫點的指令位元組)都從 FD2.EXE 讀,不寫死紀錄裡的數字。
對照:同一組「三次 lut 都錄到」的檢查套在續一百二十六借道那份紀錄(第 1 章資料),必須判為不符合。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lc126_analyze as A  # noqa: E402
from _evpaths import ROOT  # noqa: E402
RAW = ROOT / ".wsl_build"

R1 = Path(sys.argv[1]) if __name__ == "__main__" and len(sys.argv) > 1 else RAW / "lc127b_live" / "r1.json"
CTL = Path(sys.argv[2]) if __name__ == "__main__" and len(sys.argv) > 2 else RAW / "lc126_all" / "r1.json"
# cycles 2500 的兩份(lc127d,dosbox-x-c2500 包裝只換 cycles)與 cycles 5000 的兩份(續一百二十六 lc126c)
C2500 = Path(sys.argv[3]) if __name__ == "__main__" and len(sys.argv) > 3 else RAW / "lc127d_live"
C5000 = Path(sys.argv[4]) if __name__ == "__main__" and len(sys.argv) > 4 else RAW / "lc126_all"
results: list[dict] = []
LUT_CALLS = sorted(A.LUT_CALLS_22)          # 0x24978 / 0x249c4 / 0x24a10
LUT_ENTRY, LUT_FRAME = 0x2189A, 0x2198E


def check(group: str, name: str, ok: bool | None, detail: str, control: bool = False) -> None:
    results.append({"group": group, "name": name, "ok": ok, "control": control, "detail": detail})
    tag = "對照" if control else "預測"
    state = "不適用" if ok is None else ("符合" if ok else "不符合")
    print(f"[{group}] {tag} {name}: {state} —— {detail}")


def three_luts(d: dict) -> tuple[bool, str]:
    """三次 lut 入口都錄到,返回位址依序是三個呼叫點的下一條,引數等於 EXE 裡的 push。"""
    ents = A.stops(d, LUT_ENTRY)
    want = [(A.ret_after_call(c), A.LUT_CALLS_22[c]) for c in LUT_CALLS]
    # args 紀錄是 (使用者, 起始半徑, 每幀加);EXE 的 push 也是 (使用者 imm, 半徑, 每幀加)
    got = [(int(s["ret"], 16), s["args"]) for s in ents]
    ok = len(ents) == 3 and all(g[0] == w[0] and g[1] == w[1] for g, w in zip(got, want))
    return ok, f"紀錄 {[(hex(a), b) for a, b in got]},靜態 {[(hex(a), b) for a, b in want]}"


def static_checks() -> None:
    g = "S"
    check(g, "戰後表第 22 格 = 0x24754", A.HANDLER == 0x24754, hex(A.HANDLER))
    # 戰前 / 戰後章節表的呼叫點:mov eax, [0x53c03](a1 03 3c 00 00,obj2 內位移)緊接 call [eax*4 + 表](ff 14 85 disp32)
    for call, disp in ((0x25E3A, 0x1D71), (0x25F10, 0x1D71), (0x260F5, 0x1D71), (0x25E23, 0x1DE9)):
        b = A.sbytes(call - 5, 12)
        ok = b[:5] == bytes.fromhex("a1033c0000") and b[5:8] == bytes.fromhex("ff1485") and struct.unpack_from("<I", b, 8)[0] == disp
        check(g, f"{hex(call)} 以 [0x53c03] 索引 0x5{disp:04x}", ok, b.hex())
    # 三張表首尾相接:0x51d01 + 28*4 = 0x51d71,0x51d71 + 30*4 = 0x51de9;0x51e61 那格不是程式段位址
    nxt = struct.unpack("<I", A.sbytes(0x51E61, 4))[0] + 0x10000
    check(g, "表界", 0x51D01 + 28 * 4 == 0x51D71 and 0x51D71 + 30 * 4 == 0x51DE9 and not (0x10000 <= nxt < 0x50000),
          f"0x51e61 讀到 {hex(nxt)}")


def live_checks(d: dict) -> None:
    g = "L r1"
    post = A.first(d, 0x25E1E)
    check(g, "戰後表之前章節索引本來就是 22(沒有寫入)", post is not None and post["before"]["chap"] == 22 and "after" not in post,
          f"{post and post['before']}")
    check(g, "執行期戰後表第 22 格", post is not None and int(post["table_22"], 16) == A.HANDLER, f"{post and post['table_22']}")
    ent = A.first(d, 0x24754)
    check(g, "處理器入口的返回位址", ent is not None and int(ent["ret"], 16) == A.HANDLER_RET,
          f"紀錄 {ent and ent['ret']},靜態 {hex(A.HANDLER_RET)}")
    dlg = A.first(d, 0x2495D)
    check(g, "dialog 14 之前章節索引已加 1", dlg is not None and dlg["g"]["chap"] == 23 and dlg["dialog_idx"] == 14,
          f"chap {dlg and dlg['g']['chap']},dialog {dlg and dlg['dialog_idx']}")
    ok, det = three_luts(d)
    check(g, "三次 lut 的返回位址與引數", ok, det)
    fr = [s for s in d["stops"] if s.get("at") == hex(LUT_FRAME)]
    lut1 = A.LUT_CALLS_22[LUT_CALLS[0]]
    want_r = [lut1[1] + lut1[2] * k for k in range(10)]
    check(g, "lut #1 十幀、半徑 = 起始 + 每幀加 × 幀序", [s["frame"] for s in fr] == list(range(10)) and [s["radius"] for s in fr] == want_r,
          f"幀 {[s['frame'] for s in fr]},半徑 {[s['radius'] for s in fr]}")
    seq = [int(s["at"], 16) for s in d["stops"] if s.get("at", "").startswith("0x2") and 0x24754 < int(s["at"], 16) < 0x24B14]
    check(g, "處理器內停點依位址遞增", len(seq) >= 10 and all(a < b for a, b in zip(seq, seq[1:])), " -> ".join(hex(a) for a in seq))
    real = [s for s in d["stops"] if s.get("at") != "key"]
    check(g, "跑到 0x25e2a 返回、模擬器沒有結束", real[-1]["at"] == hex(A.HANDLER_RET) and not any(s["at"] == "exit" for s in real),
          f"最後一站 {real[-1]['at']}")
    # 計時:#1 逐幀停、#2 只停兩端,兩者引數相同 → tick 差應相同(停住時模擬器不跑)
    def span(n: int) -> int | None:
        ents = A.stops(d, LUT_ENTRY)
        rets = A.stops(d, A.ret_after_call(LUT_CALLS[n]))
        return rets[0]["tick"] - ents[n]["tick"] if len(ents) > n and rets else None
    s1, s2, s3 = span(0), span(1), span(2)
    check(g, "#1(逐幀停)與 #2(不停)tick 數相同", s1 is not None and s1 == s2 and lut1 == A.LUT_CALLS_22[LUT_CALLS[1]],
          f"#1 {s1},#2 {s2},#3 {s3}(BIOS tick,約 54.93 ms)")


def span_end(d: dict) -> int | None:
    """地震術入口到迴圈結束(0x21998)的 tick 數。"""
    e, z = A.first(d, LUT_ENTRY), A.first(d, 0x21998)
    return z["tick"] - e["tick"] if e and z else None


def cycles_checks(c25: dict[str, dict], c50: dict[str, dict]) -> None:
    g = "T"
    call, push = A.SPELL[11]
    for tag, d in c25.items():
        e = A.first(d, LUT_ENTRY)
        check(g, f"{tag} 入口引數與返回位址", e is not None and e["args"] == [0] + push and int(e["ret"], 16) == call + 5,
              f"紀錄 {e and (e['args'], e['ret'])},靜態 {([0] + push, hex(call + 5))}")
    fr = [s for s in c25["c2500_frames"]["stops"] if s.get("at") == hex(LUT_FRAME)]
    check(g, "c2500_frames 十幀的序號與半徑", [s["frame"] for s in fr] == list(range(10)) and
          [s["radius"] for s in fr] == [push[0] + push[1] * k for k in range(10)], f"{[(s['frame'], s['radius']) for s in fr]}")
    check(g, "c2500_nof 沒有逐幀停", not A.stops(c25["c2500_nof"], LUT_FRAME), f"{len(A.stops(c25['c2500_nof'], LUT_FRAME))} 站")
    a25 = [span_end(d) for d in c25.values()]
    a50 = [span_end(d) for d in c50.values()]
    check(g, "cycles 2500 逐幀停與不停的 tick 相同", None not in a25 and len(set(a25)) == 1, f"{a25}")
    ok = None not in a25 + a50 and all(1.6 <= x / y <= 2.6 for x in a25 for y in a50)
    check(g, "cycles 減半,tick 約變兩倍(受 CPU 限制)", ok, f"2500 {a25},5000 {a50}(1 tick 量化,容許 1.6 ~ 2.6 倍)")
    rival = None not in a25 + a50 and all(abs(x - y) <= 1 for x in a25 for y in a50)
    check("C", "對照:等垂直回掃(與 cycles 無關)的預測", rival, f"2500 {a25},5000 {a50}", control=True)


def control_check(d: dict) -> None:
    ok, det = three_luts(d)
    check("C", "續一百二十六借道紀錄(第 1 章資料)套同一檢查", ok, det, control=True)


def main() -> int:
    static_checks()
    live_checks(json.loads(R1.read_text(encoding="utf-8")))
    control_check(json.loads(CTL.read_text(encoding="utf-8")))
    cycles_checks({t: json.loads((C2500 / f"{t}.json").read_text(encoding="utf-8")) for t in ("c2500_nof", "c2500_frames")},
                  {t: json.loads((C5000 / f"{t}.json").read_text(encoding="utf-8")) for t in ("s11_nof", "s11_frames")})
    real = [r for r in results if not r["control"]]
    ctl = [r for r in results if r["control"]]
    print("預測", len(real), "符合", sum(bool(r["ok"]) for r in real), "| 對照", len(ctl), "判為不符合", sum(r["ok"] is False for r in ctl))
    bad = [f"{r['group']} {r['name']}" for r in real if not r["ok"]] + \
          [f"{r['group']} {r['name']}(對照沒有判為不符合)" for r in ctl if r["ok"] is not False]
    if bad:
        print("FAIL " + " | ".join(bad))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
