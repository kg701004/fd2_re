"""續一百二十六:lc126 / lc126b / lc126c 實機紀錄的逐項檢查(原暫存 an126.py,續一百三十四移進倉庫)。
用法:lc126_analyze.py [資料夾](預設 .wsl_build/lc126_all);ev_lut_circle_ramp_frame_time_ch22_post.py 呼叫 main()。

資料夾內:r1.json、r2.json(章節索引 22 的戰後處理器)、s11_frames.json、s11_nof.json、s12_frames.json(lut 計時)。
靜態值都從 FD2.EXE 讀(戰後表第 22 格、呼叫指令長度、push 的立即值),不寫死紀錄裡的數字。
結束碼:0 = 預測全部符合且對照全部不符合或不適用;1 = 有不符。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _evpaths import GAME, ROOT as REPO  # noqa: E402
sys.path.insert(0, str(REPO / "tools"))
import disasm_le as D  # noqa: E402

DATA = Path(sys.argv[1]) if __name__ == "__main__" and len(sys.argv) > 1 else REPO / ".wsl_build" / "lc126_all"
TICK_MS = 65536 / 1193182 * 1000   # BIOS tick 的長度(PIT 1193182 Hz / 65536)

_data = (GAME / "FD2.EXE").read_bytes()
_meta = D.parse_le(_data)
results: list[dict] = []


def sbytes(addr: int, n: int) -> bytes:
    return D.object_bytes(_data, _meta, addr, n)


def check(group: str, name: str, ok: bool | None, detail: str, control: bool = False) -> None:
    results.append({"group": group, "name": name, "ok": ok, "control": control, "detail": detail})
    tag = "對照" if control else "預測"
    state = "不適用" if ok is None else ("符合" if ok else "不符合")
    print(f"[{group}] {tag} {name}: {state} —— {detail}")


def stops(d: dict, addr: int) -> list[dict]:
    return [s for s in d["stops"] if s.get("at") == hex(addr)]


def first(d: dict, addr: int) -> dict | None:
    s = stops(d, addr)
    return s[0] if s else None


# ---- 靜態(FD2.EXE)
def post_table(idx: int) -> int:
    """戰後表 0x51de9 第 idx 格。檔案裡存的是 obj1 內的位移,載入時以 fixup 加上 obj1 基底 0x10000。"""
    return struct.unpack("<I", sbytes(0x51DE9 + idx * 4, 4))[0] + 0x10000


def ret_after_call(addr: int) -> int:
    b = sbytes(addr, 7)
    if b[0] == 0xE8:
        return addr + 5
    assert b[:3] == bytes([0xFF, 0x14, 0x85]), b.hex()   # call dword ptr [eax*4 + disp32]
    return addr + 7


def imm_pushes(call_addr: int, n: int) -> list[int]:
    """call 前面連續 n 個 push imm8(6a xx),依呼叫慣例排成 (第 1 個, 第 2 個, ...)。"""
    b = sbytes(call_addr - 2 * n, 2 * n)
    assert all(b[i] == 0x6A for i in range(0, 2 * n, 2)), b.hex()
    vals = [struct.unpack("b", b[i + 1:i + 2])[0] for i in range(0, 2 * n, 2)]
    return vals[::-1]


HANDLER = post_table(22)
HANDLER_RET = ret_after_call(0x25E23)
LUT_CALLS_22 = {0x24978: imm_pushes(0x24978, 3), 0x249C4: imm_pushes(0x249C4, 3), 0x24A10: imm_pushes(0x24A10, 3)}
# 三個呼叫點由 FD2.EXE 定(續一百三十五 sweep_literals:位址改一個 byte 也照樣讀得出 push,沒有判準擋):
# 處理器起 0x300 bytes 內所有 call rel32 到 lut_circle_ramp_at_unit(0x2189a)的位置
_hb = sbytes(HANDLER, 0x300)
_lut_sites = [HANDLER + i for i in range(len(_hb) - 4)
              if _hb[i] == 0xE8 and HANDLER + i + 5 + struct.unpack_from("<i", _hb, i + 1)[0] == 0x2189A]
assert _lut_sites == sorted(LUT_CALLS_22), [hex(x) for x in _lut_sites]
SPELL = {  # 法術 -> (呼叫點, 起始半徑與每幀加多少):command_handler_11 / 12 推的是 imm、imm,再 push dword ptr [esp + 0xc](4 bytes,使用者)
    11: (0x21883, imm_pushes(0x21883 - 4, 2)),
    12: (0x21AC2, imm_pushes(0x21AC2 - 4, 2)),
}
assert sbytes(0x21883 - 4, 4) == bytes.fromhex("ff74240c") and sbytes(0x21AC2 - 4, 4) == bytes.fromhex("ff74240c")


def handler_checks(tag: str, d: dict) -> None:
    g = f"H {tag}"
    post = first(d, 0x25E1E)
    check(g, "執行期戰後表第 22 格", post is not None and int(post["table_22"], 16) == HANDLER,
          f"紀錄 {post and post['table_22']},靜態 {hex(HANDLER)}")
    check(g, "改寫前後的章節索引", post is not None and post["before"]["chap"] == 1 and post["after"]["chap"] == 22,
          f"before {post and post['before']['chap']},after {post and post['after']['chap']}")
    ent = first(d, 0x24754)
    check(g, "處理器入口的返回位址", ent is not None and int(ent["ret"], 16) == HANDLER_RET,
          f"紀錄 {ent and ent['ret']},靜態 {hex(HANDLER_RET)}(0x25e23 的 call 長度)")
    dlg = first(d, 0x2495D)
    check(g, "dialog 14 之前章節索引已加 1", dlg is not None and dlg["g"]["chap"] == 23 and dlg["dialog_idx"] == 14,
          f"chap {dlg and dlg['g']['chap']},dialog {dlg and dlg['dialog_idx']}")
    real = [s for s in d["stops"] if s.get("at") not in ("key",)]
    last = real[-1] if real else {}
    crashed = (last.get("at") == "exit" and any("Illegal descriptor" in x for x in last.get("pane", []))) or \
              (last.get("name") == "不是設的斷點" and last.get("regs") == {})
    before_last = real[-2]["at"] if len(real) > 1 else None
    check(g, "dialog 14 之後模擬器結束、沒有進 lut", crashed and before_last == hex(0x2495D) and not stops(d, 0x2189A),
          f"最後一站 {last.get('at')} {last.get('pane', last.get('regs'))},前一站 {before_last},lut 入口 {len(stops(d, 0x2189A))} 次")


def order_check(d: dict) -> None:
    """第二次逐呼叫點停:停到的處理器內呼叫點依位址遞增(直線程式碼,只有前向分支)。"""
    seq = [int(s["at"], 16) for s in d["stops"] if s.get("at", "").startswith("0x2") and 0x24754 < int(s["at"], 16) < 0x24B14]
    ok = len(seq) >= 5 and all(a < b for a, b in zip(seq, seq[1:])) and seq[-1] == 0x2495D
    check("H r2", "處理器內停點依位址遞增、終於 dialog 14", ok, " -> ".join(hex(a) for a in seq))


def timing_checks(tag: str, d: dict, spell: int, frames: bool) -> dict:
    g = f"T {tag}"
    site, (r0, step) = SPELL[spell]
    ent, end = first(d, 0x2189A), first(d, 0x21998)
    check(g, "入口引數與返回位址", ent is not None and ent["args"] == [0, r0, step] and int(ent["ret"], 16) == site + 5,
          f"紀錄 {ent and ent['args']} {ent and ent['ret']},靜態 [0, {r0}, {step}] {hex(site + 5)}")
    fr = stops(d, 0x2198E)
    if frames:
        want = [(k, r0 + k * step) for k in range(10)]
        got = [(s["frame"], s["radius"]) for s in fr]
        check(g, "十幀的序號與半徑", got == want, f"紀錄 {got}")
    else:
        check(g, "沒有逐幀停", not fr, f"逐幀停點 {len(fr)} 個")
    check(g, "迴圈結束時 ebx = 10", end is not None and end["ebx"] == 10, f"ebx {end and end['ebx']}")
    total = end["tick"] - ent["tick"] if ent and end else None
    per = [b["tick"] - a["tick"] for a, b in zip([ent] + fr, fr + [end])] if frames and ent and end else []
    return {"tag": tag, "spell": spell, "ticks_entry_to_loop_end": total,
            "ms_entry_to_loop_end": round(total * TICK_MS, 1) if total is not None else None,
            "ms_per_frame_avg": round(total * TICK_MS / 10, 1) if total is not None else None,
            "tick_steps": per, "real_s_entry_to_loop_end": round(end["t"] - ent["t"], 1) if ent and end else None}


def main() -> int:
    results.clear()
    f = {k: json.loads((DATA / f"{k}.json").read_text(encoding="utf-8"))
         for k in ("r1", "r2", "s11_frames", "s11_nof", "s12_frames")}
    print("靜態:戰後表第 22 格", hex(HANDLER), "返回", hex(HANDLER_RET), "三次 lut 推的", LUT_CALLS_22, "法術", SPELL)
    handler_checks("r1", f["r1"])
    handler_checks("r2", f["r2"])
    order_check(f["r2"])
    t = [timing_checks("s11_frames", f["s11_frames"], 11, True), timing_checks("s11_nof", f["s11_nof"], 11, False),
         timing_checks("s12_frames", f["s12_frames"], 12, True)]
    a, b = t[0]["ticks_entry_to_loop_end"], t[1]["ticks_entry_to_loop_end"]
    check("T", "逐幀停與不停,入口到迴圈結束的 tick 相同", a is not None and a == b, f"逐幀 {a},不停 {b}")
    # 對照:假如停在除錯器時 tick 仍照實際時間走(執行中量到約 10 tick/s),逐幀那一次會多出 停住秒數 × 10 個
    extra_pred = round((t[0]["real_s_entry_to_loop_end"] - t[1]["real_s_entry_to_loop_end"]) * 10)
    check("T", "停住時 tick 照實際時間走", a is not None and b is not None and a - b >= extra_pred,
          f"這個說法預測多 {extra_pred} 個以上,紀錄多 {None if a is None or b is None else a - b}", True)
    for x in t:
        print("計時", x)
    real = [r for r in results if not r["control"]]
    ctl = [r for r in results if r["control"]]
    bad = [r for r in real if not r["ok"]] + [r for r in ctl if r["ok"]]
    print(f"預測 {len(real)} 項,符合 {sum(bool(r['ok']) for r in real)};對照 {len(ctl)} 項,"
          f"不符合 {sum(r['ok'] is False for r in ctl)},不適用 {sum(r['ok'] is None for r in ctl)}")
    globals()["timing"] = t
    if bad:
        print("FAIL", [r["group"] + " " + r["name"] for r in bad])
        return 1
    print("PASS")
    return 0


timing: list[dict] = []

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
