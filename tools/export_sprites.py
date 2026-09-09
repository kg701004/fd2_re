#!/usr/bin/env python3
"""炎龍騎士團2 — 從 FDICON.B24 導出地圖單位 Q 版 sprite(待機分鏡)給 remake。

FDICON.B24 = 1680 個 24×24 Q 版小人(原版戰場地圖單位,非 FIGANI 戰鬥全身)。
每角色一「組」= 12 sprite:**4 方向 × 3 幀**(站 / 抬左手 / 抬右手 → 待機手擺動感)。
索引 = 組×12 + 方向×3 + 幀,這條式子由 doc31 的反組譯定案(`0x1291e`/`0x12928`),
不是由圖像推測而來;`char_summary.sprite_frame_index` 是同一條式子的另一個使用端,
selftest 逐例對照兩者。方向順序(實測組 0)0-2 下、3-5 左、6-8 上、9-11 右。

輸出 <out>/fig_<grp>_f<00..11>.png(24×24 RGBA)。資產屬著作權,只在本機,不入庫。

用法:
  python3 export_sprites.py <out_dir> <grp[,grp...]> [palette.bin]
  python3 export_sprites.py --selftest
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from decode_fdicon import load, tile_img
from decode_image import load_palette

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ICON = "org_game/炎龍騎士團/FLAME2/FDICON.B24"
DEFAULT_PAL = "extracted/raw/FDOTHER/FDOTHER_000.bin"
GROUP_STRIDE = 12           # doc31:一組 = 4 方向 × 3 幀
DIR_STRIDE = 3
FRAMES = range(GROUP_STRIDE)
TOTAL_FRAMES = 1680         # doc31 記載的 FDICON 幀數 = 140 組 × 12
TILE_PX = 24


def frame_index(group: int, direction: int = 0, frame: int = 0) -> int:
    """doc31 反組譯定案的索引式:組×12 + 方向×3 + 幀。"""
    return group * GROUP_STRIDE + direction * DIR_STRIDE + frame


def main(argv):
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 3:
        print(__doc__); return 1
    out = argv[1]
    grps = [int(x) for x in argv[2].split(",") if x.strip()]
    palp = argv[3] if len(argv) > 3 else DEFAULT_PAL
    os.makedirs(out, exist_ok=True)
    d, tw, th, cnt, offs = load(ICON)
    pal = load_palette(palp)
    # 2026-09-09:原本越界的組號只是 `continue`,於是 `export_sprites out 200`
    # 印「導出 0 幀」然後 rc=0 —— 正是 char_summary 那輪命名過的「exit 0 但什麼
    # 都沒做」。要求的組號有效與否是呼叫端的錯,不是本工具該吞掉的。
    ngroups = cnt // GROUP_STRIDE
    bad = [g for g in grps if not 0 <= g < ngroups]
    if bad:
        print(f"組號超出範圍 {bad};FDICON 只有 {ngroups} 組(0..{ngroups - 1})。",
              file=sys.stderr)
        return 1
    total = 0
    for grp in grps:
        for k in FRAMES:   # fig_<grp>_f00..f11 = 方向×3+幀,drawUnitSprite 按 Dir 取
            tile_img(d, tw, th, offs, frame_index(grp) + k, cnt, pal).save(
                os.path.join(out, f"fig_{grp:03d}_f{k:02d}.png"))
            total += 1
    print(f"導出 {total} 幀({len(grps)} 角色組 × {GROUP_STRIDE},FDICON {TILE_PX}×{TILE_PX})-> {out}")
    return 0


def selftest() -> int:
    """對照 doc31 的反組譯索引式與 FDICON 的實際結構。

    刻意**沒有**釘「同方向內差異必定小於跨方向」:實測 4 組的跨方向平均差異只有
    同方向的 1.4~1.6 倍,而且分布重疊(每組都出現「同向最大 > 跨向最小」),用
    像素差異分不開方向。方向配置的權威來源是 doc31 的反組譯,不是圖像相似度。
    """
    import hashlib
    fails = []
    if not os.path.exists(ICON):
        print(f"缺少 {ICON},無法自我驗證", file=sys.stderr)
        return 1
    d, tw, th, cnt, offs = load(ICON)
    pal = load_palette(DEFAULT_PAL)

    print("(1) FDICON 結構:doc31 記載 1680 幀 = 140 組 × 12,tile 24×24")
    ok1 = cnt == TOTAL_FRAMES and (tw, th) == (TILE_PX, TILE_PX) and len(offs) == cnt
    print(f"    {'PASS' if ok1 else 'FAIL'}: {cnt} 幀(應 {TOTAL_FRAMES})、"
          f"{tw}×{th}、offset 表 {len(offs)} 筆、{cnt // GROUP_STRIDE} 組")
    if not ok1:
        fails.append(f"FDICON 結構不符:{cnt} / {tw}×{th} / {len(offs)}")

    print("\n(2) 跨工具:索引式必須與 char_summary.sprite_frame_index 逐例相同")
    # 同一條 doc31 式子有兩個使用端,兩邊各自寫一次就會各自漂移。
    import char_summary
    cases = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 2), (12, 3, 2), (139, 3, 2)]
    mism = [(c, frame_index(*c), char_summary.sprite_frame_index(*c))
            for c in cases if frame_index(*c) != char_summary.sprite_frame_index(*c)]
    ok2 = not mism and frame_index(139, 3, 2) == TOTAL_FRAMES - 1
    print(f"    {'PASS' if ok2 else 'FAIL'}: 6 例{'全同' if not mism else str(mism)}、"
          f"最後一組最後一幀 = {frame_index(139, 3, 2)}(應 {TOTAL_FRAMES - 1})")
    if not ok2:
        fails.append(f"索引式與 char_summary 不一致:{mism}")

    print("\n(3) 內容結構:一組 12 幀必須互不相同,不同組也必須不同")
    def h(i):
        return hashlib.md5(tile_img(d, tw, th, offs, i, cnt, pal).tobytes()).hexdigest()
    per_group = {g: [h(frame_index(g) + k) for k in FRAMES] for g in (0, 4, 9, 21)}
    within_ok = all(len(set(v)) == GROUP_STRIDE for v in per_group.values())
    across_ok = len({v[0] for v in per_group.values()}) == len(per_group)
    ok3 = within_ok and across_ok
    print(f"    {'PASS' if ok3 else 'FAIL'}: 4 組各自 12 幀互異={within_ok}、"
          f"4 組首幀互異={across_ok}")
    if not ok3:
        fails.append(f"內容結構不符:within={within_ok} across={across_ok}")

    print("\n(4) 本次修的 bug:越界組號必須報錯,不得 exit 0 假裝成功")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        rc_bad = main(["export_sprites", td, str(cnt // GROUP_STRIDE)])
        rc_neg = main(["export_sprites", td, "-1"])
        produced_bad = len(os.listdir(td))
        rc_ok = main(["export_sprites", td, "0"])
        produced_ok = len(os.listdir(td))
    ok4 = (rc_bad == 1 and rc_neg == 1 and produced_bad == 0
           and rc_ok == 0 and produced_ok == GROUP_STRIDE)
    print(f"    {'PASS' if ok4 else 'FAIL'}: 越界 rc={rc_bad}、負數 rc={rc_neg}("
          f"皆應 1,且產出 {produced_bad} 個檔)、正常 rc={rc_ok} 產出 {produced_ok} 幀")
    if not ok4:
        fails.append(f"越界處理不正確:{rc_bad}/{rc_neg}/{produced_bad}/{rc_ok}/{produced_ok}")

    print("\n(5) 非平凡性:方向無法由像素差異分開(所以第 (3) 題不是在測方向)")
    # 這一題是誠實記錄,不是通過條件的裝飾:它證明「用相似度判方向」會失敗,
    # 因此索引式只能來自 doc31 的反組譯——也就是第 (2) 題為什麼是必要的。
    def px(i):
        return tile_img(d, tw, th, offs, i, cnt, pal).convert("RGBA").tobytes()
    def diff(a, b):
        A, B = px(a), px(b)
        return sum(1 for x, y in zip(A, B) if x != y) / len(A)
    overlap = 0
    for g in (0, 4, 9, 21):
        base = frame_index(g)
        within = [diff(base + dr * 3 + i, base + dr * 3 + j)
                  for dr in range(4) for i in range(3) for j in range(i + 1, 3)]
        cross = [diff(base + a * 3, base + b * 3)
                 for a in range(4) for b in range(a + 1, 4)]
        if max(within) >= min(cross):
            overlap += 1
    ok5 = overlap == 4
    print(f"    {'PASS' if ok5 else 'FAIL'}: 4 組全部出現「同向最大 ≥ 跨向最小」"
          f"({overlap}/4)—— 像素差異確實分不開方向")
    if not ok5:
        fails.append(f"方向可分性假設變了:{overlap}/4 組重疊")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(FDICON 結構 + 跨工具索引式對照 + 內容結構 "
          "+ 越界報錯回歸 + 方向不可由像素分開的誠實記錄)。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
