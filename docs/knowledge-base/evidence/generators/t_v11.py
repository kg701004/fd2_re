# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十三 v11:說話者查找 0x12c60 的三個分支 + 線性 7 的值 + v9b 亂碼頭像的來源。

用法:python t_v11.py <inst> <out_dir> <tag> [max_min=90] [首批按鍵,逗號] [設定索引,逗號]
前提:v9_setup + v11_setup 已跑過(<out_dir>/v11_plan.json)。
同一個敵方回合觸發事件 0 六次(第一次在單位 48 的分派檢查);亂碼(第 0xb 條)一律不改。
第 3 條的開框碼改成 0xFFEF,運算元依 k:
  k=0 X(名冊兩筆同 id,+7 = 10 / 11)        → 預測 [0x53c1b] = 後一筆、頭像 11、開框 (6, 41, 0)
  k=1 Z(戰場單位 U 改成 id Z、+5 bit0、+7 13;名冊也有一筆 Z、+7 12) → 預測 [0x53c1b] = U、頭像 13、開框 U 的座標
  k=2 A(兩邊都沒有,線性 7 不改)              → 預測頭像 = 線性 7 原值(v10a:0)
  k=3 A,線性 7 = 0x4b                          → 預測頭像 75
  k=4 A,線性 7 = 0x89                          → 預測大小 3654、內容 = DATO.DAT[0x10:0xe56](偏移表後段 + 第 0 條開頭)
  k=5 A,線性 7 = 0xf0                          → 預測大小為負 → malloc 失敗 → 0x1125e「Out of Memory at Load」
線性 7 在 0x111ba 讀完(0x161c5 停點)後立刻還原。每次事件入口把單位 12 的座標還原(ACT7 每次把它往下移 2 格)。
"""
from __future__ import annotations

import json
import struct
import sys
import time

from drv import regs_rec, stack
from live import DELTA, ROOT, Live

inst, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
MAX_S = float(sys.argv[4]) * 60 if len(sys.argv) > 4 else 90 * 60
L = Live(inst, ROOT / out)
plan = json.loads((L.out / "v11_plan.json").read_text(encoding="utf-8"))
assert L.halt()
G = lambda a: L.d32(a + DELTA)  # noqa: E731 —— obj2 全域

DISPATCH = [0x1D87E, 0x1D94A, 0x1D9DA]
WRITERS = [0x161C5, 0x162AA, 0x163D7, 0x16453, 0x17F30, 0x1967E, 0x28F5E, 0x2967F, 0x31FF5]
BASE = DISPATCH + [0x34531, 0x112A5, 0x34543] + WRITERS
EVENT = [0x15F84, 0x164AC, 0x16188, 0x161B1, 0x165AC, 0x111BA, 0x1636C, 0x16149, 0x1125E]
X, Z, A, U = plan["X"], plan["Z"], plan["A"], plan["U"]
CFG = [{"id": X, "l7": None, "mode": "roster_dup"}, {"id": Z, "l7": None, "mode": "dead_battlefield"},
       {"id": A, "l7": None, "mode": "absent"}, {"id": A, "l7": 0x4B, "mode": "absent_l7"},
       {"id": A, "l7": 0x89, "mode": "absent_l7"}, {"id": A, "l7": 0xF0, "mode": "absent_l7"}]
if len(sys.argv) > 6:  # 只跑指定的設定(索引逗號分隔),例如 v14 只跑 5 = 線性 7 = 0xf0
    CFG = [CFG[int(i)] for i in sys.argv[6].split(",")]
LAST_K = len(CFG) - 1
OPEN_OFF = 1444  # 第 3 條開框碼在文字表內的位移(續七十一 v9a)
IVT7 = bytes.fromhex(plan["ivt_0_8"])[7]

st = {"k": -1, "in_event": False, "dstack": [], "garble": False, "done": False, "oom": False,
      "after_done_returns": 0, "trig_units": [], "l7_restore": False, "u_restore": False}
log: list[dict] = []


def set_bps(bps: list[int]) -> None:
    """只能在停住時呼叫:清掉全部再重下。"""
    L.cmd("BPDEL *")
    for a in bps:
        L.cmd(f"BP 0170:{a + DELTA:x}")


def h_dispatch(rec: dict, n: int) -> None:
    rec["unit"] = rec["esi"]
    rec["pending"] = hex(G(0x51A8F))
    if st["done"] or st["in_event"] or st["k"] >= LAST_K:
        return
    if st["k"] == -1 and rec["esi"] != 48:
        return
    st["k"] += 1
    L.sm(0x51A8F + DELTA, struct.pack("<I", 0))
    rec["trigger_k"] = st["k"]
    rec["pending_after"] = hex(G(0x51A8F))
    st["trig_units"].append(rec["esi"])


def h_ev0(rec: dict, n: int) -> None:
    rec["k"] = st["k"]
    st["in_event"] = True
    L.sm(L.ua(12, 0), bytes(plan["unit12_xy"]))
    rec["unit12_reset"] = plan["unit12_xy"]
    set_bps(BASE + EVENT)


def h_join(rec: dict, n: int) -> None:
    a = stack(L, rec, 2, f"{tag}_{n}_args")
    rec["ret"], rec["join_id"], rec["count"] = hex(a[0] - DELTA), a[1], G(0x53BFB)


def h_writer(rec: dict, n: int) -> None:
    """[0x53a85] 寫入點:EAX = 新頭像緩衝區;0x111ba 的三個引數還留在 [esp-0xc..esp)。"""
    f, old, idx = struct.unpack("<3I", L.dump(rec["esp"] - 0xC, 12, f"{tag}_{n}_wargs"))
    rec["file"], rec["old"], rec["portrait_idx"] = hex(f - DELTA), hex(old), idx
    rec["new"] = hex(rec["eax"])
    size = G(0x53BFF)
    rec["size_53bff"] = size
    rec["c67"] = hex(G(0x53C67))
    rec["k"] = st["k"]
    if rec["eax"]:
        L.dump(rec["eax"], min(size, 0x5000), f"{tag}_{n}_portrait_buf")
        rec["buf_dump"] = f"{tag}_{n}_portrait_buf.bin"
    if st["l7_restore"]:
        L.sm(7, bytes([IVT7]))
        st["l7_restore"] = False
        rec["l7_restored"] = L.dump(0, 8, f"{tag}_{n}_ivt").hex()


def h_dlg(rec: dict, n: int) -> None:
    a = stack(L, rec, 10, f"{tag}_{n}_args")
    rec["ret"], rec["table"], rec["idx"], rec["rest"] = hex(a[0] - DELTA), hex(a[1]), a[2], a[3:]
    for g in (0x53A85, 0x53C67, 0x53C1B, 0x53BFF):
        rec[hex(g)] = hex(G(g))
    rec["k"] = st["k"]
    st["dstack"].append(a[2])
    if a[2] == 0xB:
        st["garble"] = True
        L.dump(G(0x53A85), 0x5000, f"{tag}_{n}_a85_buf")
        rec["a85_dump"] = f"{tag}_{n}_a85_buf.bin"
        return
    if a[2] != 3 or not 0 <= st["k"] <= LAST_K:
        return
    cfg = CFG[st["k"]]
    t = a[1]
    code, opnd = struct.unpack("<HH", L.dump(t + OPEN_OFF, 4, f"{tag}_{n}_open"))
    rec["open_before"] = [hex(code), opnd]
    if code not in (0xFFED, 0xFFEF):
        rec["patched"] = None
        return
    if cfg["mode"] == "dead_battlefield":
        ua = L.ua(U)
        L.sm(ua + 5, bytes([plan["U_before"]["+5"] | 1]))
        L.sm(ua + 7, bytes([13, Z]))
        st["u_restore"] = True
        rec["U_after"] = L.dump(ua, 0x10, f"{tag}_{n}_U").hex()
    if cfg["l7"] is not None:
        L.sm(7, bytes([cfg["l7"]]))
        st["l7_restore"] = True
    L.sm(t + OPEN_OFF, struct.pack("<HH", 0xFFEF, cfg["id"]))
    rec["patched"] = {"mode": cfg["mode"], "char_id": cfg["id"], "l7": cfg["l7"]}
    rec["open_after"] = [hex(x) for x in struct.unpack("<HH", L.dump(t + OPEN_OFF, 4, f"{tag}_{n}_open2"))]
    rec["ivt_0_8"] = L.dump(0, 8, f"{tag}_{n}_ivt").hex()
    rec["roster_count"] = G(0x53BFB)


def h_dend(rec: dict, n: int) -> None:
    idx = st["dstack"].pop() if st["dstack"] else None
    rec["idx"], rec["k"] = idx, st["k"]
    rec["c67"] = hex(G(0x53C67))
    if idx == 0xB:
        st["garble"] = False
    if idx == 3:
        st["in_event"] = False
        if st["u_restore"]:
            ua = L.ua(U)
            b = plan["U_before"]
            L.sm(ua + 5, bytes([b["+5"]]))
            L.sm(ua + 7, bytes([b["+7"], b["+8"]]))
            st["u_restore"] = False
            rec["U_restored"] = L.dump(ua, 0x10, f"{tag}_{n}_U2").hex()
        set_bps(BASE)
        if st["k"] >= LAST_K:
            st["done"] = True


def h_spk(rec: dict, n: int) -> None:
    v = rec["eax"]
    rec["lookup_ret"] = v - (1 << 32) if v >= 0x80000000 else v
    c1b = G(0x53C1B)
    rec["c1b"] = hex(c1b)
    rp = int(plan["roster_ptr"], 16)
    if c1b and L.ubase <= c1b < L.ubase + plan["units"] * 0x50:
        rec["c1b_is"] = ["unit", (c1b - L.ubase) // 0x50]
    elif c1b and rp <= c1b < rp + 32 * 0x50:
        rec["c1b_is"] = ["roster", (c1b - rp) // 0x50]
    else:
        rec["c1b_is"] = ["other", c1b]
    if c1b:
        rec["c1b_rec16"] = L.dump(c1b, 16, f"{tag}_{n}_c1b").hex()


def h_portrait(rec: dict, n: int) -> None:
    rec["portrait_idx_ebp"], rec["edi"], rec["c1b"] = rec["ebp"], hex(rec["edi"]), hex(G(0x53C1B))
    rec["ivt_0_8"] = L.dump(0, 8, f"{tag}_{n}_ivt").hex()


def h_box(rec: dict, n: int) -> None:
    a = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["ret"], rec["x"], rec["y"], rec["flag"] = hex(a[0] - DELTA), a[1], a[2], a[3]


def h_load(rec: dict, n: int) -> None:
    a = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["ret"], rec["file"], rec["old"], rec["res_idx"] = hex(a[0] - DELTA), hex(a[1] - DELTA), hex(a[2]), a[3]


def h_open(rec: dict, n: int) -> None:
    rec["code4"] = L.dump(rec["esi"], 4, f"{tag}_{n}_code").hex()


def h_oom(rec: dict, n: int) -> None:
    rec["size_53bff"] = G(0x53BFF)
    rec["k"] = st["k"]
    st["oom"] = True
    st["done"] = True


H = {**{a: h_dispatch for a in DISPATCH}, 0x34531: h_ev0, 0x112A5: h_join, 0x34543: h_join,
     **{a: h_writer for a in WRITERS}, 0x15F84: h_dlg, 0x164AC: h_dend, 0x16188: h_spk, 0x161B1: h_portrait,
     0x165AC: h_box, 0x111BA: h_load, 0x1636C: h_open, 0x16149: h_open, 0x1125E: h_oom}


def save() -> None:
    (L.out / f"{tag}.json").write_text(json.dumps({"plan": plan, "state": st, "stops": log}, ensure_ascii=False,
                                                  indent=1), encoding="utf-8")


def main() -> None:
    set_bps(BASE)
    L.resume()
    t0 = time.time()
    idle, n, shot_n, sent = 0, 0, 0, 0
    queue = sys.argv[5].split(",") if len(sys.argv) > 5 else ["Return"]
    while time.time() - t0 < MAX_S:
        time.sleep(1.2)
        if L.running():
            idle += 1
            if idle >= 4:
                idle = 0
                if st["oom"]:
                    L.shot(f"{tag}_oom_{shot_n:03d}")
                    shot_n += 1
                    if shot_n >= 3:
                        break
                    continue
                if st["garble"]:
                    if shot_n % 6 == 0:
                        L.shot(f"{tag}_g{st['k']}_{shot_n:03d}")
                    shot_n += 1
                    continue
                k = queue.pop(0) if queue else "Return"
                L.shot(f"{tag}_s{sent:03d}_pre_{k}")
                L.key(k, 1.0)
                sent += 1
                if st["done"]:
                    st["after_done_returns"] += 1
                    if st["after_done_returns"] >= 4:
                        break
            continue
        idle = 0
        rec = regs_rec(L)
        eip = int(rec["eip"], 16)
        rec["n"] = n
        if eip in H:
            H[eip](rec, n)
        if eip in (0x15F84, 0x164AC, 0x16149, 0x1636C, 0x165AC, 0x1125E) or eip in WRITERS or "trigger_k" in rec:
            L.shot(f"{tag}_{n:03d}_{eip:x}")
        log.append(rec)
        print(json.dumps(rec, ensure_ascii=False)[:600], flush=True)
        n += 1
        save()
        L.resume()
    L.shot(f"{tag}_final")
    save()
    # 收尾:停住、清斷點、恢復(否則之後的按鍵都送進停住的遊戲)
    from live import run as hrun
    hrun(["enter-debugger", "--instance", inst])
    time.sleep(3)
    L.cmd("BPDEL *")
    L.resume()
    print("done", flush=True)


main()
