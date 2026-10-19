"""續一百二十五:lc125 兩輪實機紀錄逐項對反組譯推出的預測(原暫存 an125.py,續一百三十四移進倉庫)。
用法:lc125_analyze.py [資料夾](預設 .wsl_build/lc125_live);ev_item79_aim_exp_reward_lines.py 呼叫 main()。

三組:
  S  ai_item_candidate_select / ai_item_target_score 對道具 79(列 +0x10 > 0xf、type 0x18)的施放點、目標與評分
  E  spell_damage_apply 的經驗值累加(0x1c8a3 .. 0x1c8e2)
  K  grant_reward_rows 種類 3(0x1ac2b):payload 是目前章節文字表的字串序號
每一項有預測與對照;預測要符合,對照要不符合(與預測相同、分辨不了的記為不適用)。
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
import decode_story_text as DST  # noqa: E402
import decode_text as DT  # noqa: E402
import disasm_le as D  # noqa: E402

# 只有直接執行時才讀命令列的資料夾(被產生器 import 時 argv 是它自己的)
DATA = Path(sys.argv[1]) if __name__ == "__main__" and len(sys.argv) > 1 else REPO / ".wsl_build" / "lc125_live"
FDTXT = {n: REPO / "extracted" / "raw" / "FDTXT" / f"FDTXT_{n:03d}.bin" for n in (1, 2)}
results: list[dict] = []


def check(group: str, name: str, ok: bool | None, detail: str, control: bool = False) -> None:
    results.append({"group": group, "name": name, "ok": ok, "control": control, "detail": detail})
    tag = ("對照" if control else "預測")
    state = "不適用" if ok is None else ("符合" if ok else "不符合")
    print(f"[{group}] {tag} {name}: {state} —— {detail}")


def control(group: str, name: str, ctl_value, record_value, pred_value) -> None:
    """對照:對照值與紀錄不同 -> 對照判為不符合(有效);對照值與預測相同 -> 樣本分辨不了,記不適用。"""
    if ctl_value == pred_value:
        check(group, name, None, f"對照值 {ctl_value} 與預測相同,樣本分辨不了", True)
    else:
        check(group, name, ctl_value == record_value, f"對照值 {ctl_value},紀錄 {record_value}", True)


# ---- 靜態資料(FD2.EXE)
_data = (GAME / "FD2.EXE").read_bytes()
_meta = D.parse_le(_data)


def sbytes(addr: int, n: int) -> bytes:
    return D.object_bytes(_data, _meta, addr, n)


def high_class_exp(f7: int) -> int:
    return sbytes(0x61AF9 + (f7 - 0x44) * 10, 10)[9]


ITEM79 = sbytes(0x602AD + 79 * 0x17, 0x17)
ITEM_TYPE, ITEM_VALUE = ITEM79[0xD], struct.unpack_from("<H", ITEM79, 0xE)[0]
ITEM_RANGE = ITEM79[0x10]
SPELL3_POWER = struct.unpack_from("<H", sbytes(0x619FD + ITEM_VALUE * 7, 2), 0)[0]


# ---- 預測模型(反組譯)
def cast_cells(ux: int, uy: int, w: int, h: int, centre: bool = False) -> list[list[int]]:
    """列 +0x10 > 0xf:collect_targets_in_range(使用者, 範圍 1, 內圈門檻 1) -> 曼哈頓距離 1 的格(門檻 1 把距離 0 的中心排除),
    map_collect_cells_byte3_set 以 y 外 x 內列出。"""
    out = []
    for y in range(h):
        for x in range(w):
            d = abs(x - ux) + abs(y - uy)
            if d == 1 or (centre and d == 0):
                out.append([x, y])
    return out


def line_targets(units: list[dict], cx: int, cy: int, sx: int, sy: int, steps: int, w: int, h: int,
                 enemies: bool = False, dead: bool = False) -> list[int]:
    """build_target_candidates(cx, cy, out, sx, sy, steps, 0):同一欄時 sy > cy 往上、否則往下;不同欄時 sx > cx 往左、否則往右;
    從起點走 steps 步,出界略過;unit_at_cursor 取第一個活著且站在該格的單位;選擇子 0 收 +6 != 0。"""
    if sx == cx:
        dx, dy = 0, (-1 if sy > cy else 1)
    else:
        dx, dy = (-1 if sx > cx else 1), 0
    x, y, out = sx, sy, []
    for _ in range(steps):
        x, y = x + dx, y + dy
        if not (0 <= x < w and 0 <= y < h):
            continue
        hit = next((u for u in units if u["x"] == x and u["y"] == y and (dead or not (u["f5"] & 1))), None)
        if hit is None:
            continue
        if enemies or hit["camp"] != 0:
            out.append(hit["i"])
    return out


def score(units: list[dict], targets: list[int], value: int) -> int:
    hp = {u["i"]: u["hp"] for u in units}
    return sum(0x12 if value >= hp[t] else 8 for t in targets)


def pick(cands: list[tuple[list[int], int]], ge: bool = False) -> tuple[list[int], int]:
    best, bs = None, 0
    for cell, s in cands:
        if s > bs or (ge and s >= bs and s > 0):
            best, bs = cell, s
    return best, bs


def load(tag: str) -> dict:
    return json.loads((DATA / f"{tag}.json").read_text(encoding="utf-8"))


def at(stops: list[dict], addr: str) -> list[dict]:
    return [s for s in stops if s["at"] == addr]


def selection_full(tag: str, stops: list[dict]) -> None:
    """有單位表的那一輪:施放點、每格目標、分數、勝出者全部重算。"""
    sels = at(stops, "0x1567e")
    cells_st = at(stops, "0x1576e")
    scores = at(stops, "0x157fd")
    ends = at(stops, "0x1586a")
    check("S", f"{tag} 呼叫次數", len(sels) == len(cells_st) == len(ends) == 2,
          f"入口 {len(sels)}、施放點清單 {len(cells_st)}、掃完 {len(ends)}(ai_choose_action 的兩個呼叫點 0x1d92a / 0x14f24)")
    per_call = []
    cur = None
    for s in stops:
        if s["at"] == "0x1567e":
            cur = {"sel": s, "scores": []}
            per_call.append(cur)
        elif s["at"] == "0x1576e" and cur is not None:
            cur["cells"] = s
        elif s["at"] == "0x157fd" and cur is not None:
            cur["scores"].append(s)
        elif s["at"] == "0x1586a" and cur is not None:
            cur["end"] = s
    for k, c in enumerate(per_call):
        units, w, h = c["sel"]["units"], c["sel"]["map_w"], c["sel"]["map_h"]
        me = next(u for u in units if u["i"] == c["sel"]["unit"])
        pc = cast_cells(me["x"], me["y"], w, h)
        check("S", f"{tag}#{k} 施放點", c["cells"]["cells"] == pc, f"預測 {pc},紀錄 {c['cells']['cells']}")
        control("S", f"{tag}#{k} 施放點含中心", cast_cells(me["x"], me["y"], w, h, centre=True), c["cells"]["cells"], pc)
        steps = ITEM_RANGE - 0x10
        pred = [(cell, line_targets(units, cell[0], cell[1], me["x"], me["y"], steps, w, h)) for cell in pc]
        pred_nz = [(cell, t) for cell, t in pred if t]
        rec = [(s["cast"], s["targets"]) for s in c["scores"]]
        check("S", f"{tag}#{k} 有目標的施放點與目標", rec == pred_nz, f"預測 {pred_nz},紀錄 {rec}")
        ctl_e = [(cell, t) for cell in pc if (t := line_targets(units, cell[0], cell[1], me["x"], me["y"], steps, w, h, enemies=True))]
        control("S", f"{tag}#{k} 直線也收敵方", ctl_e, rec, pred_nz)
        ctl_d = [(cell, t) for cell in pc if (t := line_targets(units, cell[0], cell[1], me["x"], me["y"], steps, w, h, dead=True))]
        control("S", f"{tag}#{k} 直線也收陣亡", ctl_d, rec, pred_nz)
        ps = [score(units, t, ITEM_VALUE) for _, t in pred_nz]
        rs = [s["score"] for s in c["scores"]]
        check("S", f"{tag}#{k} 分數", rs == ps, f"type {ITEM_TYPE:#x} 數值 = 列 +0xe = {ITEM_VALUE};預測 {ps},紀錄 {rs}")
        control("S", f"{tag}#{k} 數值用法術威力 {SPELL3_POWER}", [score(units, t, SPELL3_POWER) for _, t in pred_nz], rs, ps)
        best, bs = pick(list(zip([c_ for c_, _ in pred_nz], ps)))
        rb = c["end"]["best"]
        check("S", f"{tag}#{k} 勝出", [rb["x"], rb["y"]] == best and rb["score"] == bs and rb["slot"] == 2,
              f"預測 {best} 分數 {bs} slot 2,紀錄 {rb}")


def selection_partial(tag: str, stops: list[dict], ref_units: list[dict]) -> None:
    """round A 的單位表沒存下來:只驗分數(目標的 HP 都 > 數值)與同分不換;目標格以 b1 的單位位置 + 擺放紀錄比對。"""
    calls = []
    cur = None
    for s in stops:
        if s["at"] == "0x1567e":
            cur = {"sel": s, "scores": []}
            calls.append(cur)
        elif s["at"] == "0x1576e":
            cur["cells"] = s
        elif s["at"] == "0x157fd":
            cur["scores"].append(s)
        elif s["at"] == "0x1586a":
            cur["end"] = s
    placed = {p[0]: (p[1], p[2]) for p in calls[0]["sel"].get("placed", [])}
    units = [dict(u, hp=u["mhp"], f5=0) if u["i"] in placed else dict(u) for u in ref_units]
    for u in units:
        if u["i"] in placed:
            u["x"], u["y"] = placed[u["i"]]
    only = [u for u in units if u["i"] in (0, 3, 5, 10, 11)]
    for k, c in enumerate(calls):
        me = next(u for u in only if u["i"] == 11)
        w, h = c["sel"]["map_w"], c["sel"]["map_h"]
        pc = cast_cells(me["x"], me["y"], w, h)
        check("S", f"{tag}#{k} 施放點", c["cells"]["cells"] == pc, f"預測 {pc},紀錄 {c['cells']['cells']}")
        rec = [(s["cast"], s["targets"]) for s in c["scores"]]
        pred = [(cell, t) for cell in pc if (t := line_targets(only, cell[0], cell[1], me["x"], me["y"], ITEM_RANGE - 0x10, w, h))]
        check("S", f"{tag}#{k} 目標(只用 #0 #3 #5 #10 #11 的位置)", rec == pred, f"預測 {pred},紀錄 {rec}")
        ps = [score(only, t, ITEM_VALUE) for _, t in rec]
        rs = [s["score"] for s in c["scores"]]
        check("S", f"{tag}#{k} 分數", rs == ps, f"預測 {ps},紀錄 {rs}(目標 HP 取 b1 單位表的 MaxHP;NPC 在 round A 之前沒有受傷)")
        control("S", f"{tag}#{k} 數值用法術威力 {SPELL3_POWER}", [score(only, t, SPELL3_POWER) for _, t in rec], rs, ps)
        best, bs = pick(list(zip([s["cast"] for s in c["scores"]], ps)))
        rb = c["end"]["best"]
        check("S", f"{tag}#{k} 同分不換", [rb["x"], rb["y"]] == best and rb["score"] == bs, f"預測 {best} 分數 {bs},紀錄 {rb}")
        lb, _ = pick(list(zip([s["cast"] for s in c["scores"]], ps)), ge=True)
        control("S", f"{tag}#{k} 同分改換(>=)", lb, [rb["x"], rb["y"]], best)


def exp_checks(tag: str, stops: list[dict], ref_units: list[dict]) -> None:
    info = {u["i"]: u for u in ref_units}
    adds = at(stops, "0x1c8e2")
    loop = at(stops, "0x20fe5")
    total = 0
    for s in adds:
        u = info[s["unit"]]
        base = high_class_exp(u["f7"]) * u["lv"]
        pred = base if s["edi_new_hp"] == 0 else base * s["ebp_damage"] // u["mhp"]
        total += s["eax_add"]
        check("E", f"{tag} #{s['unit']} 累加", s["eax_add"] == pred,
              f"表 +9 = {high_class_exp(u['f7'])} × 等級 {u['lv']}" + ("(陣亡,不縮放)" if s["edi_new_hp"] == 0 else
                                                                    f" × 傷害 {s['ebp_damage']} / MaxHP {u['mhp']}") + f" = {pred},紀錄 {s['eax_add']}")
        control("E", f"{tag} #{s['unit']} 一律不縮放", base, s["eax_add"], pred)
        control("E", f"{tag} #{s['unit']} 一律縮放", base * s["ebp_damage"] // u["mhp"], s["eax_add"], pred)
        if s["edi_new_hp"]:
            control("E", f"{tag} #{s['unit']} 除以新 HP", base * s["ebp_damage"] // s["edi_new_hp"], s["eax_add"], pred)
    check("E", f"{tag} 迴圈結束的 [0x53ec8]", len(loop) == 1 and loop[0]["exp"] == total,
          f"累加合計 {total},紀錄 {[x['exp'] for x in loop]}")
    hit = [s["unit"] for s in adds]
    low = [i for i in hit if info[i]["f7"] < 0x44]
    check("E", f"{tag} +7 < 0x44 的目標沒有累加停點", not low, f"有停點的目標 {hit}")


def kind3_checks(tag: str, stops: list[dict], ref_units: list[dict], dead: list[int]) -> None:
    fs = {n: DT.parse_strings(str(p)) for n, p in FDTXT.items()}
    boxes = {b["string_index"]: b for b in DST.script_boxes(str(FDTXT[2]))}
    grant = at(stops, "0x21072")
    k3 = at(stops, "0x1ac2b")
    rows = bytes.fromhex(grant[0]["rows"]) if grant else b""
    n = grant[0]["args"][1] if grant else 0
    want = [struct.unpack_from("<H", rows, 3 * i + 1)[0] for i in range(n) if rows[3 * i] == 3]
    check("K", f"{tag} 種類 3 停點的 payload", [s["payload"] for s in k3] == want,
          f"獎勵列 {rows[:3 * n].hex()} -> {want},紀錄 {[s['payload'] for s in k3]}")
    reward = {u["i"]: u["reward"] for u in ref_units}
    pays = [int.from_bytes(bytes.fromhex(reward[i])[1:3], "little") for i in dead]
    check("K", f"{tag} payload 來自陣亡單位的 +0x31..0x33", want == pays and all(reward[i][:2] == "03" for i in dead),
          f"陣亡 {dead} 的獎勵列 {[reward[i] for i in dead]}")
    for s in k3:
        p = s["payload"]
        ok2 = s.get("file_match", {}).get("FDTXT_002") is True
        check("K", f"{tag} 第 {p} 條 = FDTXT_002 第 {p} 條", ok2 and p < len(fs[2]),
              f"執行期字碼與檔案字串相同 = {s.get('file_match')};FDTXT_002 有 {len(fs[2])} 條")
        # 對照主張「文字表是 FDTXT_001」:那麼執行期字碼應等於 FDTXT_001 的第 p 條(紀錄是實際比對結果)
        control("K", f"{tag} 第 {p} 條當成 FDTXT_001", True, s.get("file_match", {}).get("FDTXT_001"), False)
        b = boxes.get(p)
        spk = b["operand"] if b and b["speaker_kind"] == "runtime" else None
        # payload 不在獎勵列裡時不能 index(突變測試抓到這裡會丟 ValueError),直接判不符合
        check("K", f"{tag} 第 {p} 條的說話者", spk in dead and p in want and dead.index(spk) == want.index(p),
              f"開框碼 0xFFEC/0xFFED 運算元 = unit {spk};台詞 {' / '.join(b['lines']) if b else None}")
        check("K", f"{tag} 第 {p} 條用 [0x53a79]", s["txt_ptr"] == at(stops, "0x15055")[0]["table"]["txt_ptr"] if at(stops, "0x15055") else True,
              f"0x1ac2b 讀到 {s['txt_ptr']}")


def main() -> int:
    results.clear()
    a1, a1b, b1 = load("a1"), load("a1b"), load("b1")
    ref = at(b1["stops"], "0x1567e")[0]["units"]
    print(f"靜態:道具 79 列 {ITEM79.hex()}(type {ITEM_TYPE:#x}、+0xe {ITEM_VALUE}、+0x10 {ITEM_RANGE:#x});法術 {ITEM_VALUE} 威力 {SPELL3_POWER}")
    for tag, st in (("a1", a1["stops"]), ("b1", b1["stops"])):
        e = at(st, "0x15055")[0]["table"]
        check("K", f"{tag} 入口的文字表", e["FDTXT_002"]["diff_bytes"] == 0 and e["FDTXT_001"]["diff_bytes"] > 0,
              f"[0x53a79] = {e['txt_ptr']};與 FDTXT_002 差 {e['FDTXT_002']['diff_bytes']} bytes、FDTXT_001 差 {e['FDTXT_001']['diff_bytes']} bytes")
    selection_partial("a1", a1["stops"], ref)
    selection_full("b1", b1["stops"])
    exp_checks("a1", a1["stops"], ref)
    exp_checks("b1", b1["stops"], ref)
    kind3_checks("a1", a1["stops"] + a1b["stops"], ref, [5, 10])
    b_grant = at(b1["stops"], "0x21072")
    check("K", "b1 沒有陣亡 -> 筆數 0、沒有種類 3 停點", b_grant[0]["args"][1] == 0 and not at(b1["stops"], "0x1ac2b"),
          f"grant_reward_rows 引數 {b_grant[0]['args']}")
    real = [r for r in results if not r["control"]]
    ctl = [r for r in results if r["control"]]
    bad = [r for r in real if not r["ok"]] + [r for r in ctl if r["ok"]]
    print(f"預測 {len(real)} 項,符合 {sum(bool(r['ok']) for r in real)};對照 {len(ctl)} 項,不符合 {sum(r['ok'] is False for r in ctl)}、"
          f"不適用 {sum(r['ok'] is None for r in ctl)}")
    if bad:
        print("FAIL", [r["group"] + " " + r["name"] for r in bad])
        return 1
    print("ALL-OK")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
