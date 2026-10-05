# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十二 v10a:亂碼畫面頭像的來源(項目 1)與 0xFFEF 說話者不在戰場也不在名冊(項目 3)。

用法:python t_v10a.py <inst> <out_dir> <tag> [max_min=40]
同一個敵方回合觸發事件 0 三次(第一次在單位 48 的分派檢查,之後每次在上一個事件結束後的下一個分派檢查):
  k=0 亂碼:不改(自然)        ;第 3 條:不改(自然,0xFFED 單位 16 → 載入龍的頭像)
  k=1 亂碼:[0x53c67] = 0x9017 ;第 3 條:開框碼改 0xFFEF、運算元 = 只在名冊的角色 id(正對照)
  k=2 亂碼:arg8(動畫旗標)= 0  ;第 3 條:開框碼改 0xFFEF、運算元 = 不在戰場也不在名冊的角色 id
斷點:分派檢查、0x34531、0x112a5、0x34543、[0x53a85] 的 9 個寫入點(全程);
事件期間另加 0x15f84、0x164ac、0x16559、0x16188、0x161b1、0x165ac、0x111ba、0x1636c、0x16149。
亂碼播放期間不送鍵(0x10620 偵測到按鍵會把 arg8 清 0、停掉動畫);其餘時間閒置就送 Return。
"""
from __future__ import annotations

import json
import struct
import sys
import time

from drv import regs_rec, stack
from live import DELTA, ROOT, Live

inst, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
MAX_S = float(sys.argv[4]) * 60 if len(sys.argv) > 4 else 40 * 60
L = Live(inst, ROOT / out)
assert L.halt()
G = lambda a: L.d32(a + DELTA)  # noqa: E731 —— obj2 全域

DISPATCH = [0x1D87E, 0x1D94A, 0x1D9DA]
WRITERS = [0x161C5, 0x162AA, 0x163D7, 0x16453, 0x17F30, 0x1967E, 0x28F5E, 0x2967F, 0x31FF5]
BASE = DISPATCH + [0x34531, 0x112A5, 0x34543] + WRITERS
EVENT = [0x15F84, 0x164AC, 0x16559, 0x16188, 0x161B1, 0x165AC, 0x111BA, 0x1636C, 0x16149]
CFG = [{"garble": None, "idx3": None}, {"garble": "pos9017", "idx3": "roster_only"},
       {"garble": "noanim", "idx3": "absent"}]
OPEN_OFF = 1444  # 第 3 條開框碼在文字表內的位移(續七十一 v9a)

st = {"k": -1, "in_event": False, "dstack": [], "garble": False, "a559_armed": False, "a559_hits": 0,
      "done": False, "after_done_returns": 0, "trig_units": []}
log: list[dict] = []
cur_bps: list[int] = []


def set_bps(bps: list[int]) -> None:
    """只能在停住時呼叫:清掉全部再重下。"""
    global cur_bps
    L.cmd("BPDEL *")
    for a in bps:
        L.cmd(f"BP 0170:{a + DELTA:x}")
    cur_bps = list(bps)


def cur() -> dict:
    sx, sy, cx, cy = struct.unpack("<4i", L.dump(0x53AA9 + DELTA, 16, "cur"))
    return {"scroll": [sx, sy], "cursor": [cx, cy]}


def ids_state() -> tuple[list[int], list[int]]:
    n = G(0x53BEB) & 0xFF
    ub = G(0x53A45)
    u = L.dump(ub, n * 0x50, f"{tag}_ids_units")
    rn, rp = G(0x53BFB), G(0x53BF7)
    r = L.dump(rp, min(rn, 32) * 0x50, f"{tag}_ids_roster")
    return [u[i * 0x50 + 8] for i in range(n)], [r[i * 0x50 + 8] for i in range(min(rn, 32))]


def h_dispatch(rec: dict, n: int) -> None:
    rec["unit"] = rec["esi"]
    rec["pending"] = hex(G(0x51A8F))
    if st["done"] or st["in_event"] or st["k"] >= 2:
        return
    if st["k"] == -1 and rec["esi"] != 48:
        return
    st["k"] += 1
    L.sm(0x51A8F + DELTA, struct.pack("<I", 0))
    rec["trigger_k"] = st["k"]
    rec["pending_after"] = hex(G(0x51A8F))
    rec.update(cur())
    st["trig_units"].append(rec["esi"])


def h_ev0(rec: dict, n: int) -> None:
    rec["k"] = st["k"]
    st["in_event"] = True
    set_bps(BASE + EVENT)
    st["a559_armed"] = True


def h_join(rec: dict, n: int) -> None:
    a = stack(L, rec, 2, f"{tag}_{n}_args")
    rec["ret"], rec["join_id"], rec["count"] = hex(a[0] - DELTA), a[1], G(0x53BFB)


def h_writer(rec: dict, n: int) -> None:
    """[0x53a85] 寫入點:EAX = 新頭像緩衝區;0x111ba 的三個引數還留在 [esp-0xc..esp)。"""
    a = L.dump(rec["esp"] - 0xC, 12, f"{tag}_{n}_wargs")
    f, old, idx = struct.unpack("<3I", a)
    rec["file"], rec["old"], rec["portrait_idx"] = hex(f - DELTA), hex(old), idx
    rec["new"] = hex(rec["eax"])
    rec["size_53bff"] = G(0x53BFF)
    rec["c67"] = hex(G(0x53C67))
    L.dump(rec["eax"], 0x4000, f"{tag}_{n}_portrait_buf")
    rec["buf_dump"] = f"{tag}_{n}_portrait_buf.bin"


def h_dlg(rec: dict, n: int) -> None:
    a = stack(L, rec, 10, f"{tag}_{n}_args")
    rec["ret"], rec["table"], rec["idx"], rec["rest"] = hex(a[0] - DELTA), hex(a[1]), a[2], a[3:]
    for g in (0x53A85, 0x53C67, 0x53C1B, 0x53BFF):
        rec[hex(g)] = hex(G(g))
    rec["k"] = st["k"]
    st["dstack"].append(a[2])
    cfg = CFG[st["k"]] if 0 <= st["k"] < 3 else {"garble": None, "idx3": None}
    if a[2] == 0xB:
        st["garble"] = True
        st["a559_hits"] = 0
        L.dump(G(0x53A85), 0x4000, f"{tag}_{n}_a85_buf")
        rec["a85_dump"] = f"{tag}_{n}_a85_buf.bin"
        if cfg["garble"] == "pos9017":
            L.sm(0x53C67 + DELTA, struct.pack("<I", 0x9017))
        elif cfg["garble"] == "noanim":
            L.sm(rec["esp"] + 0x24, struct.pack("<I", 0))
        rec["control"] = cfg["garble"]
        rec["after_c67"] = hex(G(0x53C67))
        rec["after_arg8"] = struct.unpack("<I", L.dump(rec["esp"] + 0x24, 4, f"{tag}_{n}_a8"))[0]
    elif a[2] == 3:
        st["a559_idx3"] = 0
        set_bps(BASE + EVENT)
    if a[2] == 3 and cfg["idx3"]:
        t = a[1]
        code, opnd = struct.unpack("<HH", L.dump(t + OPEN_OFF, 4, f"{tag}_{n}_open"))
        rec["open_before"] = [hex(code), opnd]
        units, roster = ids_state()
        rec["battle_ids"], rec["roster_ids"] = units, roster
        if cfg["idx3"] == "roster_only":
            cand = [i for i in roster if i not in units and i != 0x27]
        else:
            cand = [i for i in range(1, 0x80) if i not in units and i not in roster and i != 0x27]
        if code == 0xFFED and cand:
            cid = cand[0]
            L.sm(t + OPEN_OFF, struct.pack("<HH", 0xFFEF, cid))
            rec["patched"] = {"mode": cfg["idx3"], "char_id": cid}
            rec["open_after"] = [hex(x) for x in struct.unpack("<HH", L.dump(t + OPEN_OFF, 4, f"{tag}_{n}_open2"))]
        else:
            rec["patched"] = None
        rec["ivt_0_8"] = L.dump(0, 8, f"{tag}_{n}_ivt").hex()


def h_dend(rec: dict, n: int) -> None:
    idx = st["dstack"].pop() if st["dstack"] else None
    rec["idx"], rec["k"] = idx, st["k"]
    rec["c67"] = hex(G(0x53C67))
    if idx == 0xB:
        st["garble"] = False
        rec["a559_hits_during_garble"] = st["a559_hits"]
    if idx == 3:
        st["in_event"] = False
        set_bps(BASE)
        if st["k"] >= 2:
            st["done"] = True


def h_559(rec: dict, n: int) -> None:
    a = stack(L, rec, 2, f"{tag}_{n}_args")
    rec["ret"], rec["frame"] = hex(a[0] - DELTA), a[1]
    rec["a85"], rec["c67"], rec["k"] = hex(G(0x53A85)), hex(G(0x53C67)), st["k"]
    rec["in_garble"] = st["garble"]
    if st["garble"]:
        st["a559_hits"] += 1
    # k=0/1 只記第一次(每兩個字模一次,上千次);k=2 整段亂碼都留著(預期 0 次),第 3 條只記到 3 次
    if not st["garble"]:
        st["a559_idx3"] = st.get("a559_idx3", 0) + 1
    keep = (st["k"] == 2 and st["garble"]) or (not st["garble"] and st.get("a559_idx3", 0) < 3)
    if not keep:
        set_bps([b for b in cur_bps if b != 0x16559])


def h_spk(rec: dict, n: int) -> None:
    v = rec["eax"]
    rec["lookup_ret"] = v - (1 << 32) if v >= 0x80000000 else v
    rec["c1b"] = hex(G(0x53C1B))


def h_portrait(rec: dict, n: int) -> None:
    rec["portrait_idx_ebp"], rec["edi"], rec["c1b"] = rec["ebp"], hex(rec["edi"]), hex(G(0x53C1B))


def h_box(rec: dict, n: int) -> None:
    a = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["ret"], rec["x"], rec["y"], rec["flag"] = hex(a[0] - DELTA), a[1], a[2], a[3]
    rec.update(cur())


def h_load(rec: dict, n: int) -> None:
    a = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["ret"], rec["file"], rec["old"], rec["res_idx"] = hex(a[0] - DELTA), hex(a[1] - DELTA), hex(a[2]), a[3]


def h_open(rec: dict, n: int) -> None:
    rec["code4"] = L.dump(rec["esi"], 4, f"{tag}_{n}_code").hex()


H = {**{a: h_dispatch for a in DISPATCH}, 0x34531: h_ev0, 0x112A5: h_join, 0x34543: h_join,
     **{a: h_writer for a in WRITERS}, 0x15F84: h_dlg, 0x164AC: h_dend, 0x16559: h_559, 0x16188: h_spk,
     0x161B1: h_portrait, 0x165AC: h_box, 0x111BA: h_load, 0x1636C: h_open, 0x16149: h_open}


def main() -> None:
    set_bps(BASE)
    L.resume()
    t0 = time.time()
    idle, n, shot_n, sent = 0, 0, 0, 0
    # 開頭按鍵(第 5 個引數,逗號分隔);預設只送 Return(圈已開、[0x53c57] 已設成 3 = 待機)
    queue = sys.argv[5].split(",") if len(sys.argv) > 5 else ["Return"]
    while time.time() - t0 < MAX_S:
        time.sleep(1.2)
        if L.running():
            idle += 1
            if idle >= 4:
                idle = 0
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
        if eip in (0x15F84, 0x164AC, 0x16149, 0x1636C, 0x165AC) or eip in WRITERS or "trigger_k" in rec:
            L.shot(f"{tag}_{n:03d}_{eip:x}")
        log.append(rec)
        print(json.dumps(rec, ensure_ascii=False)[:600], flush=True)
        n += 1
        L.resume()
    L.shot(f"{tag}_final")
    (L.out / f"{tag}.json").write_text(json.dumps({"state": st, "stops": log}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    # 收尾:停住、清斷點、恢復(否則之後的按鍵都送進停住的遊戲)
    from live import run as hrun
    hrun(["enter-debugger", "--instance", inst])
    time.sleep(3)
    L.cmd("BPDEL *")
    L.resume()
    print("done", flush=True)


main()
