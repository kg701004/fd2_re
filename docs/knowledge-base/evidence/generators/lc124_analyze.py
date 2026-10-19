"""續一百二十四:把 lc124 三輪實機紀錄逐項對靜態預測,另配會判不符合的對照(原暫存 an124.py,續一百三十四移進倉庫)。

由 ev_rest_and_item79_branch.py 呼叫 main();原始紀錄在 .wsl_build/lc124_live/。
每一項印 PASS / FAIL;對照項(control)預期 FAIL,實際 FAIL 才算對照有效。算不出來的一律 FAIL。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from _evpaths import GAME, ROOT  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as DL  # noqa: E402

D = ROOT / ".wsl_build" / "lc124_live"
RUNS = ("r1", "r2", "r3")
W, H = 320, 200
VX, VY, VW, VH = 4, 4, 312, 192        # 視窗在 VGA 上的位置(copy_rect 到 0xa0504,312 x 192)
results: list[dict] = []


def check(name: str, ok: bool, detail: str, control: bool = False) -> None:
    results.append({"name": name, "ok": bool(ok), "control": control, "detail": detail})
    tag = ("PASS" if ok else "FAIL") if not control else ("對照 FAIL(有效)" if not ok else "對照 PASS(無效!)")
    print(f"[{tag}] {name}: {detail}")


def control(name: str, wrong_pred: object, right_pred: object, actual: object) -> None:
    """對照:錯的預測與對的預測相同時,這個樣本分辨不了,記為不適用(不算有效、也不算無效)。"""
    if wrong_pred == right_pred:
        results.append({"name": name, "ok": None, "control": True, "detail": f"與正確預測相同({right_pred}),不適用"})
        print(f"[對照 不適用] {name}: 與正確預測相同({right_pred})")
        return
    check(name, wrong_pred == actual, f"預測 {wrong_pred},實際 {actual}", True)


def load(tag: str) -> list[dict]:
    return json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))["stops"]


def first(stops: list[dict], at: str) -> dict | None:
    return next((s for s in stops if s["at"] == at), None)


def unit(stop: dict, i: int) -> dict:
    return next(u for u in stop["units"] if u["i"] == i)


# ---------- 1. 休息 ----------
def rest_pred(hp: int, mhp: int, poison: int, para: int, rounding: bool = False) -> int | None:
    """rest_hp_recover:HP == MaxHP 或中毒 / 麻痺時不寫(回 None);否則 min(HP + MaxHP / 5, MaxHP)(整數除法)。"""
    if hp == mhp or poison or para:
        return None
    q = round(mhp / 5) if rounding else mhp // 5
    return min(hp + q, mhp)


def rest_checks() -> None:
    for tag in RUNS:
        st = load(tag)
        ring = first(st, "0x19077")
        ent = first(st, "0x13fd4")
        w = first(st, "0x1410a")
        ret = first(st, "0x19087")
        entry = first(st, "0x15055")
        if ring is None:
            check(f"{tag} 休息", False, "沒有停到指令環 0x19077")
            continue
        moved = ring["moved_flag"]
        if moved:
            # 預測:移動過就不呼叫 rest_hp_recover,HP 保持 arm 時寫的值
            ok = ent is None and ret is None and entry is not None and unit(entry, 0)["hp"] == 3
            check(f"{tag} 移動後休息不回血", ok,
                  f"moved_flag={moved} rest 入口={'有' if ent else '無'} ai_item_action 入口時索爾 HP={unit(entry, 0)['hp'] if entry else '?'}")
            # 對照:假設休息不看移動旗標 → 預測 HP 會變成 3 + 823/5
            if entry is not None:
                p = rest_pred(3, 823, 0, 0)
                control(f"{tag} 對照:休息不看移動旗標", p, 3, unit(entry, 0)["hp"])
            continue
        if ent is None or ret is None:
            check(f"{tag} 休息", False, "rest_hp_recover 入口或返回沒停到")
            continue
        row = ent["row"]
        p = rest_pred(row["hp"], row["mhp"], row["poison"], row["para"])
        after = ret["units"][0]["hp"]
        if p is None:
            ok = w is None and ret["eax"] == 0 and after == row["hp"]
            check(f"{tag} 休息(滿血)", ok, f"HP {row['hp']}/{row['mhp']} 預測不寫、回 0;寫入站={'有' if w else '無'} 回傳 {ret['eax']} 之後 HP {after}")
        else:
            ok = w is not None and w["edi_new_hp"] == p and w["eax_quot"] == row["mhp"] // 5 and ret["eax"] == 1 and after == p
            check(f"{tag} 休息", ok, f"HP {row['hp']} + {row['mhp']}//5 = {p};寫入前 EDI {w['edi_new_hp'] if w else '?'} 商 {w['eax_quot'] if w else '?'};"
                  f" 回傳 {ret['eax']};之後 HP {after};返回位址 {ent['ret']}")
            pr = rest_pred(row["hp"], row["mhp"], row["poison"], row["para"], rounding=True)
            control(f"{tag} 對照:四捨五入", pr, p, w["edi_new_hp"] if w else None)


# ---------- 2. 傷害 ----------
def per_target(stops: list[dict]) -> list[dict]:
    """把每一次 spell_damage_resolve 入口到返回之間的站收成一筆。"""
    out, cur = [], None
    for s in stops:
        if s["at"] == "0x1c75e":
            cur = {"res": s}
        elif cur is not None:
            key = {"0x1c7ed": "base", "0x1c7fe": "roll", "0x1c816": "miss", "0x1c81f": "apply", "0x1c87f": "roll2",
                   "0x1c897": "sub", "0x20fd0": "ret", "0x20fae": "popn", "0x20fdb": "popf"}.get(s["at"])
            if key:
                cur[key] = s
            if s["at"] in ("0x20fae", "0x20fdb"):
                out.append(cur)
                cur = None
    return out


def damage_checks(static_resist: list[int], static_row3: bytes) -> None:
    for tag in RUNS:
        st = load(tag)
        end = first(st, "0x20fe5")
        tg = per_target(st)
        disp = first(st, "0x20c6f")
        if disp is None or end is None:
            check(f"{tag} 傷害", False, "沒有 item_effect_dispatch 入口或迴圈結束")
            continue
        check(f"{tag} 目標個數", len(tg) == disp["count"], f"dispatch count {disp['count']},逐目標 {len(tg)} 筆")
        for k, t in enumerate(tg):
            r, b = t["res"], t.get("base")
            u = r["row"]
            name = f"{tag} 目標 #{u['i']}"
            if b is None:
                check(name, False, "沒有 0x1c7ed")
                continue
            row = bytes.fromhex(b["spell_row"])
            power = struct.unpack_from("<h", row, 0)[0]
            live_res = b["resist_tbl"]
            base = power * live_res[u["cls"] - 1] // 10
            check(f"{name} 基礎傷害", b["esi_base"] == base and r["spell"] == 3,
                  f"法術 {r['spell']} 威力 {power} × 魔抗表[職業 {u['cls']} - 1] {live_res[u['cls'] - 1]} / 10 = {base};實際 {b['esi_base']}")
            bad = power * live_res[u["cls"]] // 10 if u["cls"] < 28 else None
            control(f"{name} 對照:魔抗表不減 1", bad, base, b["esi_base"])
            hit = row[2]
            roll = t["roll"]["edx_roll"]
            if roll < hit:
                if "apply" not in t or "sub" not in t:
                    check(f"{name} 命中", False, f"亂數 {roll} < 命中 {hit} 應命中,但沒有 spell_damage_apply")
                    continue
                r2 = t["roll2"]["edx_roll"]
                dmg = base * 9 // 10 + r2 * base // 1000
                hp_after = max(0, u["hp"] - dmg)
                got_after = unit(end, u["i"])["hp"]
                ok = (t["sub"]["ebp_damage"] == dmg and t["ret"]["eax"] == dmg and t["popn"]["args"] == [dmg, 0x5E, u["i"]]
                      and got_after == hp_after and "miss" not in t)
                check(f"{name} 命中與傷害", ok,
                      f"亂數 {roll} < {hit} 命中;{base}×9//10 + {r2}×{base}//1000 = {dmg};扣 HP 前 EBP {t['sub']['ebp_damage']},"
                      f" 回傳 {t['ret']['eax']},跳字 {t['popn']['args']};HP {u['hp']} -> 預測 {hp_after} 實際 {got_after}")
                other = [x for x in tg if x is not t and "roll2" in x]
                if other:
                    r2o = other[0]["roll2"]["edx_roll"]
                    dmg_o = base * 9 // 10 + r2o * base // 1000
                    control(f"{name} 對照:用另一個目標的傷害亂數", dmg_o, dmg, t["sub"]["ebp_damage"])
            else:
                ok = "miss" in t and "apply" not in t and t["ret"]["eax"] == 0 and t.get("popf", {}).get("args") == [u["i"]] \
                    and unit(end, u["i"])["hp"] == u["hp"]
                check(f"{name} 沒命中", ok, f"亂數 {roll} >= 命中 {hit};回 {t['ret']['eax']},固定跳字 {t.get('popf', {}).get('args')},"
                      f" HP {u['hp']} -> {unit(end, u['i'])['hp']}")
            check(f"{name} 對照:命中判定反過來", (roll >= hit) == ("apply" in t), f"亂數 {roll} 命中 {hit}", True)
        # 跳字佇列
        exp_g, exp_dx, exp_o = [], [], []
        for t in tg:
            u = t["res"]["row"]["i"]
            if "popn" in t:
                s = str(t["popn"]["args"][0])
                for i in range(4):
                    j = i - (4 - len(s))
                    exp_g.append(0 if j < 0 else 0x5E + int(s[j]))
                    exp_dx.append(i * 5 + 2)
            else:
                exp_g += [0x74, 0x75, 0x76, 0x76]
                exp_dx += [2, 8, 12, 17]
            exp_o += [u] * 4
        got = (bytes.fromhex(end["glyph"]), bytes.fromhex(end["dx"]), bytes.fromhex(end["owner"]))
        check(f"{tag} 跳字佇列", (list(got[0]), list(got[1]), list(got[2])) == (exp_g, exp_dx, exp_o) and end["popups"] == len(exp_g),
              f"預測字形 {bytes(exp_g).hex()} 位移 {bytes(exp_dx).hex()} 所屬 {bytes(exp_o).hex()};實際 {end['glyph']} {end['dx']} {end['owner']}")
        left = []
        for t in tg:
            if "popn" in t:
                s = str(t["popn"]["args"][0])
                left += [0x5E + int(c) for c in s] + [0] * (4 - len(s))
            else:
                left += [0x74, 0x75, 0x76, 0x76]
        control(f"{tag} 對照:數字靠左", bytes(left).hex(), bytes(exp_g).hex(), got[0].hex())
        # 表格與靜態影像
        b0 = next((t["base"] for t in tg if "base" in t), None)
        if b0 is not None:
            check(f"{tag} 魔抗表 = EXE 靜態 0x51f96", b0["resist_tbl"] == static_resist, f"{b0['resist_tbl'][:8]}…")
            want = bytearray(static_row3)
            if tag == "r2":
                want[2] = 0          # 本輪在記憶體裡把命中率改成 0
            check(f"{tag} 法術列 3 = EXE 靜態 0x61a12(r2 命中率改 0)", bytes.fromhex(b0["spell_row"]) == bytes(want),
                  f"靜態 {static_row3.hex()},實際 {b0['spell_row']},執行期位址 {b0['spell_row_at']}(+0x19c000 讀到的線性)")


# ---------- 3. 畫面 ----------
def vga(name: str) -> bytes | None:
    f = D / f"{name}.bin"
    return f.read_bytes() if f.exists() else None


def unit_rect(ux: int, uy: int, sx: int, sy: int, margin: int) -> tuple[int, int, int, int]:
    """單位格在 VGA 上的範圍(blit 起點是格子左上再往上 6 列),加上 margin。"""
    x0 = VX + (ux - sx) * 24
    y0 = VY + (uy - sy) * 24 - 6
    return (x0 - margin, y0 - margin, x0 + 24 + margin, y0 + 30 + margin)


def changed(a: bytes, b: bytes) -> list[int]:
    return [i for i in range(W * H) if a[i] != b[i]]


def inside(i: int, rects: list[tuple[int, int, int, int]]) -> bool:
    x, y = i % W, i // W
    return any(r[0] <= x < r[2] and r[1] <= y < r[3] for r in rects)


def visible(r: tuple[int, int, int, int]) -> bool:
    return r[0] < VX + VW and r[2] > VX and r[1] < VY + VH and r[3] > VY


def frame_checks(tbls: dict) -> None:
    """動畫與收尾:相鄰兩幀比較(每幀都從同一份存下的畫面重畫,背景相同);閃爍:對 play_map_effect_animation 返回時的畫面比較。

    每一處改動都要落在畫面內目標格(含 margin)裡,每個畫面內目標都要有改動;
    對照把目標格往左移 5 格,改動不該全落在移位後的格子裡。
    """
    for tag in RUNS:
        st = load(tag)
        call = first(st, "0x20f80")
        if call is None:
            continue
        sx, sy = call["g"]["scroll_x"], call["g"]["scroll_y"]
        tg = bytes.fromhex(call["targets"])
        disp = first(st, "0x20c6f")
        pos = {u["i"]: (u["x"], u["y"]) for u in disp["units"]}
        anim = [s for s in st if s["at"] == "0x1c640"]
        n = tbls["count"][3]
        check(f"{tag} 動畫幀數", [s["k"] for s in anim] == list(range(n)) and all(s["anim"] == 3 for s in anim),
              f"表 0x51f54[3] = {n};實際幀序 {[s['k'] for s in anim]}")
        fl = [s["k"] for s in st if s["at"] == "0x1cd8e"]
        check(f"{tag} 閃爍幀數", fl == list(range(10)), f"實際 {fl}")
        fin = [s["k"] for s in st if s["at"] == "0x1dfd7"]
        full = first(st, "0x20ff4") is not None
        check(f"{tag} 收尾幀數" + ("" if full else "(本輪中途斷線,只看前段)"),
              fin == list(range(22)) if full else fin == list(range(len(fin))), f"實際 {len(fin)} 幀")
        for kind, pairs, margin in (
                ("動畫", [(f"{tag}_anim{k - 1:02d}", f"{tag}_anim{k:02d}") for k in range(1, len(anim))], 24),
                ("閃爍", [(f"{tag}_ret20f85_00", f"{tag}_flash{k:02d}") for k in range(len(fl))], 0),
                ("收尾", [(f"{tag}_fin{k - 1:02d}", f"{tag}_fin{k:02d}") for k in range(1, len(fin))], 24)):
            rects = {t: unit_rect(*pos[t], sx, sy, margin) for t in tg}
            vis = [t for t in tg if visible(unit_rect(*pos[t], sx, sy, 0))]
            good = [rects[t] for t in vis]
            wrong = [unit_rect(pos[t][0] - 5, pos[t][1], sx, sy, margin) for t in vis]
            tot = outside = wrong_in = 0
            hit_each = {t: 0 for t in vis}
            distinct = set()
            missing = False
            for a_name, b_name in pairs:
                a, b = vga(a_name), vga(b_name)
                if a is None or b is None:
                    missing = True
                    break
                distinct.add(b)
                c = changed(a, b)
                tot += len(c)
                outside += sum(1 for i in c if not inside(i, good))
                wrong_in += sum(1 for i in c if inside(i, wrong))
                for t in vis:
                    hit_each[t] += sum(1 for i in c if inside(i, [rects[t]]))
            if missing or not pairs:
                check(f"{tag} {kind}畫面", False, "有幀沒傾印或沒有幀")
                continue
            ok = tot > 0 and outside == 0 and all(v > 0 for v in hit_each.values()) and bool(vis)
            check(f"{tag} {kind}畫面只動在目標格", ok,
                  f"{len(pairs)} 組比較、{len(distinct)} 種畫面;共改 {tot} 像素,目標格外 {outside};"
                  f"各目標格內 {hit_each}(畫面內目標 {vis},畫面外 {[t for t in tg if t not in vis]})")
            check(f"{tag} {kind}對照:目標格往左移 5 格", wrong_in == tot, f"移位後格內 {wrong_in} / {tot}", True)


def main() -> int:
    data = (GAME / "FD2.EXE").read_bytes()
    meta = DL.parse_le(data)
    static_resist = list(struct.unpack("<28i", DL.object_bytes(data, meta, 0x51F96, 112)))
    static_row3 = DL.object_bytes(data, meta, 0x619FD + 3 * 7, 7)
    tbls = {"first": DL.object_bytes(data, meta, 0x51F33, 33), "count": DL.object_bytes(data, meta, 0x51F54, 33),
            "sfx": DL.object_bytes(data, meta, 0x51F75, 33)}
    c = first(load("r1"), "0x20f80")
    check("動畫表 = EXE 靜態(0x51f33 / 0x51f54 / 0x51f75)",
          (c["tbl_first_frame_1f33"], c["tbl_frame_count_1f54"], c["tbl_sfx_1f75"]) == (tbls["first"].hex(), tbls["count"].hex(), tbls["sfx"].hex()),
          f"動畫 3:起始幀 {tbls['first'][3]}、幀數 {tbls['count'][3]}、音效 {tbls['sfx'][3]}")
    rest_checks()
    damage_checks(static_resist, static_row3)
    frame_checks(tbls)
    real = [r for r in results if not r["control"]]
    ctl = [r for r in results if r["control"]]
    bad = [r["name"] for r in real if not r["ok"]] + [r["name"] for r in ctl if r["ok"] is True]
    print(f"\n檢查 {len(real)} 項,PASS {sum(bool(r['ok']) for r in real)};對照 {len(ctl)} 項,有效(FAIL)"
          f"{sum(r['ok'] is False for r in ctl)}、不適用 {sum(r['ok'] is None for r in ctl)}")
    print("不符合:", bad if bad else "無")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n",
                                                               encoding="utf-8", newline="\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
