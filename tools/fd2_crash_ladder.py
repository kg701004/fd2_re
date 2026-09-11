#!/usr/bin/env python3
"""fd2_crash_ladder.py — 用階梯式單變因測試,找出讓 FD2.EXE 退回 DOS 的那個動作。

背景
----
2026-09-04 已用同實例對照確立:`fd2_battle_autoplay --attack` 會讓遊戲退回 DOS,
不含 `--attack` 的同樣三回合則不會(見交接檔 C.10)。但**攻擊本身沒有執行**
(`select_ring` 回報環選到 2 就退出),所以死因不在攻擊結算,而在 `--attack`
才會走的 `approach_then_act` 那條路上的某個動作。

兩條路徑的差異只有幾個動作:

    rest_unit(活)        : 選單位 → 確認原地 → ↓ → 確認
    approach_then_act(死): 選單位 → **方向鍵移動** → 確認**新落點** → ↑ → 確認 ×2

⛔ **這支工具的前提已被推翻(2026-09-04,交接檔 C.12),結果不可讀成「排除」**
----------------------------------------------------------------------
整個階梯建立在「同樣的條件會得到同樣的結果」之上。**那是錯的**:退回 DOS 是**機率性**的。
`--dest computed --mv 4 --attack` 是刻意設計的「應該會死」對照組,卻跑滿三回合存活——
而完全相同的配置先前在 6 個不同實例上死了 6 次。

因此本檔跑出來的「A-G 八輪全部存活」**不構成排除**,只能讀成
「該次取樣下未觸發」。當時的紀錄寫成「六階全部排除」,強度遠高於證據所能支撐。

階段定義本身仍然有用(它們是精確、可重現的動作序列),但要拿來下結論,
應該交給 `fd2_trial_runner.py`:**每個條件跑 N 次全新實例、比較發生率**,
而不是看單次或少數幾輪的結果。

⛔ **第二個獨立的問題(2026-09-09):階梯在結構上就不是單變因**
------------------------------------------------------------
上面那段講的是統計前提被推翻(崩潰是機率性的)。另有一個**結構性**的問題,
與取樣無關,而且一直沒人查:設計說「一次只加一個動作」,但把各階段的動作序列
從 AST 靜態抽出來逐一比對(`stage_actions()`,`--selftest` 每次重算)後:

    stage_b -> stage_c   新增 3、移除 2
    stage_c -> stage_d   新增 3、移除 1   (cancel 被換成 ring+confirm×2)
    stage_d -> stage_e   新增 7、移除 1   (前置游標移動 7 步,且移動選格內的
                                          right 由 2 步減為 1 步)

**沒有任何一對相鄰階段只差一個動作。** 所以「死在哪一階就鎖定哪個動作」這條
推論在結構上就不成立——即使崩潰是確定性的,某一階死了也指不出是新增的哪一個
動作造成的。這不是取樣問題,是設計問題,而且完全離線可驗。

階段本身仍然是精確、可重現的動作序列,拿來當「條件」餵給 `fd2_trial_runner.py`
比較發生率仍然有效;不能用的是**階梯式歸因**。要真的隔離單一動作,得重新設計
成相鄰階段確實只差一個動作的序列——那是新的實驗設計工作,不在本次範圍。

方法(原始設計,保留供追溯)
----------------------------
一次只加一個動作(**實測不成立,見上**),每階段重複 N 輪並在每輪後用**畫面**判存活,
死在哪一階就鎖定哪個動作。
階梯刻意包含一個**已知會活**的階段(B),當作正對照——若連 B 都死,就代表死因不在
這幾個動作,而在更外層(例如 `ensure_browse` 本身或單純的重複次數)。
⚠ 這個設計的盲點正是上面那條:它假設「沒死 = 該動作無害」。

    A  ensure_browse 單獨重複
    B  A + 選單位 + 確認原地 + ↓ + 確認        (= rest_unit,已知會活)
    C  A + 選單位 + **移動** + 確認新落點       (不碰指令環)
    D  C + ↑ + 確認 ×2                        (= approach_then_act 全套)

⚠ 存活判定一律用 `H.game_alive()`(多幀畫面)。**不要用記憶體**:退回 DOS 後
`[0x53a45]`/`[0x53beb]` 仍留著舊值,單位陣列有時讀成全 0、有時讀出成功但是垃圾的
12 筆——兩者都與「暫時性壞讀」無法分辨(交接檔 C.9)。

用法
----
    python tools/fd2_crash_ladder.py --instance lad1 --rounds 4
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_battle_autoplay as A  # noqa: E402
import fd2_dosbox_live_helper as H  # noqa: E402

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


_round_no = {"n": 0}
PROVE_EVERY = 4          # 每幾輪做一次「有證明的」層級復位


def browse_reset(inst: str) -> None:
    """把 UI 帶回瀏覽層。**大部分輪次用便宜版,每 PROVE_EVERY 輪做一次有證明的版本。**

    為什麼可以省:`ensure_browse` 的完整版每次要 30-60 秒(BPDEL、6 次取消、下斷點、
    確認、讀 EIP、再 BPDEL、退回),佔了每輪約 70 秒裡的大頭。而它是**每一階都相同的
    設定步驟,不是受測變因**——階段 A 已經證明它單獨跑 16 輪無害。

    為什麼不能全省:層級一旦漂移,後續按鍵會送錯層,測試會**悄悄地**失去意義
    (本專案反覆踩過這個坑)。所以保留週期性的**有證明**復位當作漂移偵測:
    便宜版只做「無條件退到底」(Escape 在瀏覽層是 no-op),完整版才下斷點自證。
    """
    _round_no["n"] += 1
    if _round_no["n"] % PROVE_EVERY == 1:
        A.ensure_browse(inst)                 # 有證明的版本
    else:
        for _ in range(6):                    # 便宜版:只退到底
            A.press(inst, "cancel", 1.0)


def stage_a(inst: str) -> None:
    A.ensure_browse(inst)                     # A 測的就是它本身,不可替換


def stage_b(inst: str) -> None:
    browse_reset(inst)
    A.press(inst, "confirm", 1.6)          # 選單位 → 移動選格
    A.press(inst, "confirm", 2.0)          # 確認原地 → 開環
    A.select_ring(inst, A.RING_REST, "down")
    A.press(inst, "confirm", 2.5)


def stage_c(inst: str) -> None:
    browse_reset(inst)
    A.press(inst, "confirm", 1.6)          # 選單位 → 移動選格
    A.press(inst, "right", 0.8)            # **移動到新格**
    A.press(inst, "right", 0.8)
    A.press(inst, "confirm", 2.2)          # 確認新落點
    A.press(inst, "cancel", 1.2)           # 退出,不碰指令環


def stage_d(inst: str) -> None:
    browse_reset(inst)
    A.press(inst, "confirm", 1.6)
    A.press(inst, "right", 0.8)
    A.press(inst, "right", 0.8)
    A.press(inst, "confirm", 2.2)          # 確認新落點 → 開環
    A.select_ring(inst, A.RING_ATTACK, "up")
    A.press(inst, "confirm", 2.5)
    A.press(inst, "confirm", 2.5)


def stage_e(inst: str) -> None:
    """D + **在瀏覽層跨地圖移動游標**。

    2026-09-04:A-D 各跑到 16 輪都不死,而同一個實例緊接著跑一次
    `autoplay --attack` 就退回 DOS(正對照,證明實例本身有能力死)。
    所以死因在 autoplay 做、階梯沒做的事,而 `move_cursor` 是其中最明顯的一項——
    階梯永遠只操作游標當下那個單位,autoplay 則會把游標移到指定單位。
    """
    browse_reset(inst)
    for _ in range(4):                     # 跨地圖移動游標(autoplay 的 move_cursor)
        A.press(inst, "right", 0.7)
    for _ in range(3):
        A.press(inst, "down", 0.7)
    A.press(inst, "confirm", 1.6)
    A.press(inst, "right", 0.8)
    A.press(inst, "confirm", 2.2)
    A.select_ring(inst, A.RING_ATTACK, "up")
    A.press(inst, "confirm", 2.5)
    A.press(inst, "confirm", 2.5)


READS_PER_ROUND = 10


def stage_f(inst: str) -> None:
    """**反覆的 debugger 讀取循環**(autoplay 的 snapshot),UI 動作只做一次。

    第一版是「每輪先跑完整的 stage_e,再讀 3 次」,那把成本花在錯的地方:
    UI 動作在 C/D/E 已經各自被排除過,**受測變因是讀取本身**。
    每輪重跑那些動作只是讓一輪從 ~25 秒變成 ~70 秒,而且把兩個變因混在一起。

    改成:UI 動作只做一次把層級帶回瀏覽層,然後把讀取次數拉高。
    一次 `mem_read_unit_array` 要做簽章搜尋(2MB dump)+ 陣列 dump,
    所以「讀取密度」才是這一階真正在施加的壓力——autoplay 每個單位動作前後都做一次。
    """
    browse_reset(inst)
    for _ in range(READS_PER_ROUND):
        H.enter_debugger(inst)
        H.wait_halted(inst)
        H.mem_read_unit_array(inst, "0170",
                              H.DEFAULT_SHOT_DIR / inst / "ladder", num_records=12)
        H.resume(inst)
        time.sleep(0.2)


STAGES = [
    ("A  ensure_browse 單獨", stage_a),
    ("B  + 原地確認 + 休息(已知會活,正對照)", stage_b),
    ("C  + 移動到新格 + 確認落點(不碰環)", stage_c),
    ("D  + 指令環 ↑ + 確認 ×2(全套)", stage_d),
    ("E  + 瀏覽層跨地圖移動游標", stage_e),
    ("F  + 反覆讀單位陣列(autoplay 的 snapshot)", stage_f),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--rounds", type=int, default=4, help="每階段重複幾輪")
    ap.add_argument("--only", help="只跑指定階段,例如 C")
    a = ap.parse_args()

    alive, m = H.game_alive(a.instance)
    print(f"起點:{'存活' if alive else '**已離開**'} "
          f"(幀 {[f['distinct_colors'] for f in m['frames']]})", flush=True)
    if not alive:
        print("起點就不在了,無法測試")
        return 2

    for label, fn in STAGES:
        if a.only and not label.startswith(a.only):
            continue
        print(f"\n===== 階段 {label} =====", flush=True)
        for r in range(1, a.rounds + 1):
            fn(a.instance)
            alive, m = H.game_alive(a.instance)
            frames = [f["distinct_colors"] for f in m["frames"]]
            print(f"  第 {r} 輪:{'存活' if alive else '**已離開**'}  幀 {frames}", flush=True)
            if not alive:
                print(f"\n*** 死在階段【{label}】第 {r} 輪 ***")
                print("*** 該階段比前一個通過的階段多出的動作,就是嫌疑動作 ***")
                return 1
            time.sleep(0.5)
        print(f"  階段 {label}:{a.rounds} 輪全部存活", flush=True)

    print("\n全部階段都存活——死因不在這些動作裡,需要擴大階梯")
    return 0


def stage_actions() -> dict[str, list[str]]:
    """從**本檔自己的 AST** 抽出每個階段的動作序列,依原始碼順序、迴圈展開。

    為什麼靜態抽而不是執行:階段本身每一步都在驅動 DOSBox,執行不了;但「這一階
    到底做了哪些動作、順序如何」是原始碼裡就寫死的資訊,而階梯式歸因能不能成立
    只取決於那個序列。所以這是可以離線驗死的部分,也正是先前沒人查的部分。

    第一版用 `ast.walk` 取序列——**那是廣度優先,不是原始碼順序**,於是
    `stage_e` 的前置游標移動被排到尾端;而且沒有展開 `for _ in range(n)`,
    7 步的游標移動被算成 2 步。兩個錯疊在一起會讓 D->E 看起來只差 1 個動作,
    正好得出「設計沒問題」的相反結論。
    """
    import ast
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    def walk(node, mult=1):
        out: list[str] = []
        for stmt in getattr(node, "body", []):
            if isinstance(stmt, ast.For):
                n, it = 1, stmt.iter
                if (isinstance(it, ast.Call) and getattr(it.func, "id", "") == "range"
                        and it.args and isinstance(it.args[0], ast.Constant)):
                    n = it.args[0].value
                out += walk(stmt, mult * n)
                continue
            for sub in ast.walk(stmt):
                if not isinstance(sub, ast.Call):
                    continue
                f = sub.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                # 2026-09-11:突變測試把這裡的 sub.args[1] 改成 sub.args[2] 逃掉了。
                # 查過:本檔全部 22 個 `.press(...)` 呼叫都恰好是 3 個引數
                # (inst, key名稱, 計時 float),而 args[2] 同樣是 ast.Constant——
                # 所以這個檢查改看哪一個引數,對現有呼叫形狀給出同一個真假值,
                # 是量出來的等價突變,不是取樣沒打到。真正取值的那行(下面
                # `out += [sub.args[1].value] * mult`)沒被動到,值本身仍然對 ——
                # 這正是被 (5) 題(stage_e 的逐元素斷言)驗過的部分。
                if name == "press" and len(sub.args) >= 2 and isinstance(sub.args[1], ast.Constant):
                    out += [sub.args[1].value] * mult
                elif name == "select_ring":
                    a = sub.args[1] if len(sub.args) > 1 else None
                    out += ["ring:" + (ast.unparse(a) if a is not None else "?")] * mult
                elif name in ("browse_reset", "ensure_browse"):
                    out += [f"<{name}>"] * mult
        return out

    # 只取 `stage_<單一字母>`:本檔另有 `stage_actions`/`stage_deltas` 這兩個
    # 也以 stage_ 開頭的輔助函式,寬鬆的前綴判準會把它們當成階段(自己的
    # selftest 當場抓到——長度多出兩個 0 的項目)。
    return {n.name: walk(n) for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and len(n.name) == len("stage_x") and n.name.startswith("stage_")}


def stage_deltas() -> dict[str, tuple[int, int]]:
    """相鄰階段之間 (新增動作數, 移除動作數)。單變因設計要求兩者合計為 1。"""
    import difflib
    st = stage_actions()
    order = ["stage_b", "stage_c", "stage_d", "stage_e"]
    out = {}
    for a, b in zip(order, order[1:]):
        sm = difflib.SequenceMatcher(None, st[a], st[b])
        adds = dels = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("insert", "replace"):
                adds += j2 - j1
            if tag in ("delete", "replace"):
                dels += i2 - i1
        out[f"{a}->{b}"] = (adds, dels)
    return out


# 2026-09-09 實測值。釘住的是**設計不成立**這個事實,不是某個理想值——把它們
# 改成 (1, 0) 需要重新設計階段序列,那時這些數字本來就該一起改。
MEASURED_DELTAS = {"stage_b->stage_c": (3, 2), "stage_c->stage_d": (3, 1),
                   "stage_d->stage_e": (7, 1)}
STAGE_LENGTHS = {"stage_a": 1, "stage_b": 5, "stage_c": 6, "stage_d": 8,
                 "stage_e": 14, "stage_f": 1}


def selftest() -> int:
    """階梯的**設計**是否支撐它宣稱的推論。實機執行不在範圍內——但「這個階梯
    能不能隔離單一動作」根本不需要執行就能判,而那正是先前沒人查的部分。"""
    fails = []
    st = stage_actions()

    print("(1) 六個階段都抽得出動作序列,長度與實測相符")
    lens = {k: len(v) for k, v in st.items()}
    ok1 = lens == STAGE_LENGTHS
    print(f"    {'PASS' if ok1 else 'FAIL'}: {lens}")
    if not ok1:
        fails.append(f"階段序列長度漂移:{lens} != {STAGE_LENGTHS}")

    print("\n(2) **單變因設計不成立**:沒有一對相鄰階段只差一個動作")
    # 這一題釘的是問題本身。docstring 原本寫「一次只加一個動作,死在哪一階就
    # 鎖定哪個動作」——若真的成立,每個 delta 應該是 (1, 0)。
    deltas = stage_deltas()
    single = [k for k, (a, d) in deltas.items() if a + d == 1]
    ok2 = deltas == MEASURED_DELTAS and not single
    print(f"    {'PASS' if ok2 else 'FAIL'}: {deltas}、其中真正單變因的 {single or '無'}")
    if not ok2:
        fails.append(f"階段差異漂移:{deltas}")

    print("\n(3) 兩個已被推翻的前提必須都還寫在 docstring 裡")
    # 結論不可讀成「排除」有兩個獨立理由(機率性 + 結構性)。任一段被刪掉,
    # 下一個讀的人就會重新把八輪存活讀成排除。
    doc = __doc__ or ""
    ok3 = ("機率性" in doc and "不構成排除" in doc
           and "結構上就不是單變因" in doc and "沒有任何一對相鄰階段只差一個動作" in doc)
    print(f"    {'PASS' if ok3 else 'FAIL'}: 統計前提與結構前提的警告都在")
    if not ok3:
        fails.append("已被推翻的前提警告被刪除")

    print("\n(4) 階段互不相同,且 B 仍是那個已知會活的正對照")
    seqs = {k: tuple(v) for k, v in st.items()}
    dup = len(seqs) != len(set(seqs.values()))
    b_is_rest = "ring:A.RING_REST" in st["stage_b"] and "ring:A.RING_ATTACK" not in st["stage_b"]
    ok4 = not dup and b_is_rest
    print(f"    {'PASS' if ok4 else 'FAIL'}: 六階序列互異={not dup}、"
          f"B 走的是待機(不是攻擊)={b_is_rest}")
    if not ok4:
        fails.append(f"階段重複或 B 不再是正對照:dup={dup} b_rest={b_is_rest}")

    print("\n(5) 抽取器本身:順序與迴圈展開必須正確")
    # 第一版用 ast.walk(廣度優先)且不展開 range(),兩個錯疊起來會讓 D->E
    # 看起來只差 1 個動作,得出「設計沒問題」的相反結論。
    e = st["stage_e"]
    ok5 = (e[0] == "<browse_reset>" and e[1:8] == ["right"] * 4 + ["down"] * 3
           and e[-1] == "confirm" and len(e) == 14)
    print(f"    {'PASS' if ok5 else 'FAIL'}: stage_e 前置 4×right+3×down 在序列開頭、"
          f"總長 {len(e)}")
    if not ok5:
        fails.append(f"抽取器順序或迴圈展開不正確:{e}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(序列長度 + 單變因設計不成立的實測 + 兩個前提警告 "
          "+ 階段互異與正對照 + 抽取器順序)。實機執行未涵蓋,見 docstring。")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
