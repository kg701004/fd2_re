#!/usr/bin/env python3
"""炎龍騎士團2 — 角色總覽 summary:每組 FDICON 地圖 sprite + DATO face 頭像 + 組號。

驗證並一覽「統一角色編號」(doc 31):角色 id N → FDICON 組 N(地圖 sprite,
index = 組×12 + 方向×3 + 幀,反組譯 `0x1291e`/`0x12928`)+ DATO_N(對話頭像,
4 嘴型,取 m0)。140 組排成一張,方便挑角色 / 對 face / 加新人時看缺號。

前置:`extracted/fdicon/`(decode_fdicon.py)、`extracted/portraits/`(decode_dato.py)。
輸出本機 PNG(著作權,不入庫)。

用法:
  python3 char_summary.py <out.png> [groups=140] [cols=10]
  python3 char_summary.py --selftest
"""
import sys, os, json
from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARACTERS_JSON = os.path.join(REPO, "docs", "data", "exe_tables", "characters.json")

# 註:角色 id = 肖像(FA)= sprite組 = 角色,基本態恆等(青衫 memory.md 權威,doc 31)。
# 我方 0–31 一律讀 docs/data/exe_tables/characters.json,不再硬編。
# 2026-09-09:原本硬編的 NAMES 只到 21,22–31(卡里斯…渥德)這 10 個已入庫的角色
# 在總覽表上是無名的——而註解本身就已經指向 characters.json 了。同一輪也發現
# render_story.py 有一份「從未被使用」的完整肖像名表,反而比這裡在用的還齊。
# characters.json 沒有的通用/敵方組號才留在下面:
EXTRA_NAMES = {68: "士兵", 76: "士兵(援軍)", 96: "盜賊", 97: "盜賊頭目", 103: "獸人"}

SPRITE_STRIDE = 12      # doc31:FDICON index = 組×12 + 方向×3 + 幀
GROUPS_DEFAULT = 140    # doc31:FDICON 共 1680 幀 ≈ 140 組×12


def load_names(path=CHARACTERS_JSON):
    names = dict(EXTRA_NAMES)
    with open(path, encoding="utf-8") as fh:
        for c in json.load(fh):
            names[c["index"]] = c["name"]
    return names


def character_label(group, names):
    return str(group) + (" " + names[group] if group in names else "")


def sprite_frame_index(group, pose=0, cycle=0):
    return group * SPRITE_STRIDE + pose * 3 + cycle


def main(argv):
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest()
    # 2026-09-03:兩個輸入目錄都不存在時直接報錯,而不是安靜產出一張只有標籤、
    # 沒有任何 sprite/頭像的空表(每個 os.path.exists 都是 False,迴圈照跑,
    # exit 0)。全工具驗證時就是靠「exit 0 但完全沒有輸出訊息」發現的。
    missing = [d for d in ("extracted/fdicon", "extracted/portraits")
               if not os.path.isdir(d)]
    if len(missing) == 2:
        print("缺少輸入目錄 " + str(missing) +
              ";請先跑 decode_fdicon.py 與 decode_dato.py。", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 1
    if missing:
        print(f"警告:{missing} 不存在,該欄會留白", file=sys.stderr)
    names = load_names()
    out = argv[1] if len(argv) > 1 else "extracted/remake_shots/character_summary.png"
    ngrp = int(argv[2]) if len(argv) > 2 else GROUPS_DEFAULT
    cols = int(argv[3]) if len(argv) > 3 else 10
    rows = (ngrp + cols - 1) // cols
    sp, fc = 44, 40
    cw, ch = sp + fc + 6, sp + 14
    sheet = Image.new("RGB", (cols * cw, rows * ch), (25, 25, 32))
    dr = ImageDraw.Draw(sheet)
    for g in range(ngrp):
        cx, cy = (g % cols) * cw, (g // cols) * ch
        spp = f"extracted/fdicon/icon_{sprite_frame_index(g):04d}.png"
        if os.path.exists(spp):
            im = Image.open(spp).convert("RGBA").resize((sp, sp), Image.NEAREST)
            sheet.paste(im, (cx, cy + 12), im)
        fp = f"extracted/portraits/DATO_{g:03d}_m0.png"
        if os.path.exists(fp):
            fm = Image.open(fp).convert("RGBA").resize((fc, fc), Image.NEAREST)
            sheet.paste(fm, (cx + sp + 4, cy + 12), fm)
        dr.text((cx + 1, cy + 1), character_label(g, names), fill=(255, 235, 120))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print(f"角色總覽 {ngrp} 組(sprite+face)-> {out} {sheet.size}")
    return 0


# 遊戲自己的名字表:FDTXT 資源 0 的字模渲染後人工轉錄,證據圖已入庫,且其中
# 13 個名字與 2026-09-07 實機讀出的 ch27 名冊逐一吻合。這是**權威來源**。
NAME_TABLE = os.path.join(REPO, "docs", "data", "fdtxt000_name_table.json")

# 改讀 JSON 前硬編在本檔裡的 0–21。
# 2026-09-09 訂正:第 (2) 題原本要求「換來源後必須與這張舊表逐一相同」——那是
# **驗兩個副本一致,不是驗與權威來源一致**,於是它把錯誤鎖住了。舊表的 id15 是
# 「賽可邦勒」,而遊戲自己的名字表寫的是「塞可邦勒」;`decode_story_text.PORT`
# 早在 2026-08-30 就照權威表改對,`characters.json` 沒跟著改,而我這張硬編表
# 是從 characters.json 抄的,於是三處一起錯。舊值保留在下面純粹當**歷史對照**,
# 用來證明修正確實發生過,不再當成「必須相同」的基準。
OLD_NAMES_0_21_BEFORE_2026_09_09 = {
    0: "索爾", 1: "哈諾", 2: "鐵諾", 3: "哈瓦特", 4: "亞雷斯", 5: "洛娜", 6: "萊汀",
    7: "蘭斯洛特", 8: "希莉亞", 9: "悠妮", 10: "瑪琳", 11: "索菲亞", 12: "凱麗",
    13: "貝克威", 14: "珊", 15: "賽可邦勒", 16: "凱拉斯", 17: "米亞斯多德", 18: "蜜蒂",
    19: "羅德曼", 20: "莎拉", 21: "約拿",
}
# 權威表與舊表不一致的三筆(2026-09-09 修正)。
CORRECTED_NAMES = {15: ("賽可邦勒", "塞可邦勒"), 28: ("達克賽", "達克塞"),
                   29: ("亞奇梅吉", "亞齊梅吉")}
# 2026-09-09 補上的缺口(舊表完全沒有這 10 人)。id28/29 用權威表的寫法——
# 第一版從 characters.json 抄,連同那兩個錯字一起抄了進來,是第 (1) 題自己抓到的。
GAP_22_31 = {
    22: "卡里斯", 23: "羅蘭", 24: "希爾法", 25: "謝多", 26: "聖寇拉斯",
    27: "巴拿羅西亞", 28: "達克塞", 29: "亞齊梅吉", 30: "蓋亞", 31: "渥德",
}


def selftest() -> int:
    """本檔的圖片組裝需要 extracted/fdicon 與 extracted/portraits(不入庫),
    本機通常沒有,故自我驗證只涵蓋名稱表與索引公式這兩塊純邏輯——這是刻意的
    範圍限制,不是「跑過了」。"""
    fails = []
    names = load_names()

    print("(1) 本次修的缺口:22–31 這 10 個已入庫角色必須有名字")
    miss = [g for g in GAP_22_31 if g not in names]
    wrong = [(g, names.get(g), GAP_22_31[g]) for g in GAP_22_31
             if g in names and names[g] != GAP_22_31[g]]
    ok1 = not miss and not wrong
    print(f"    {'PASS' if ok1 else 'FAIL'}: 缺 {miss}、不符 {wrong}")
    if not ok1:
        fails.append(f"22–31 名稱缺口未補齊:{miss} {wrong}")

    print("\n(2) 與**權威來源**一致:遊戲自己的名字表,不是另一份副本")
    # 這一題原本問的是「換來源後有沒有跟舊硬編表一致」。那是驗兩個副本互相一致,
    # 而兩個副本可以一起錯——實際上就一起錯了三筆(見 CORRECTED_NAMES)。
    # 現在改成對 fdtxt000_name_table.json 逐一核對:那是把 FDTXT 字模渲染後人工
    # 轉錄的,證據圖已入庫,且 13 個名字與實機讀出的 ch27 名冊吻合。
    with open(NAME_TABLE, encoding="utf-8") as fh:
        auth = json.load(fh)["character_names_by_id"]
    diff = [(g, names.get(g), auth[str(g)]) for g in range(32)
            if str(g) in auth and names.get(g) != auth[str(g)]]
    ok2 = not diff and len(auth) >= 32
    print(f"    {'PASS' if ok2 else 'FAIL'}: 32 筆與權威表逐一相同"
          if ok2 else f"    FAIL: {diff}")
    if not ok2:
        fails.append(f"與權威名字表不符:{diff}")

    print("\n(2b) 修正確實發生過:三個舊名不得再出現在任何一處")
    # 沒有這一題,第 (2) 題在「權威表也被改成舊值」時仍會通過。這裡釘住的是
    # **差異本身**,不是任一邊的值。
    stale = {g: (old, new) for g, (old, new) in CORRECTED_NAMES.items()
             if names.get(g) == old or auth.get(str(g)) == old}
    still_new = all(names.get(g) == new for g, (_, new) in CORRECTED_NAMES.items())
    ok2b = not stale and still_new
    print(f"    {'PASS' if ok2b else 'FAIL'}: 三筆皆為修正後的值={still_new}、"
          f"殘留舊值 {stale or '無'}")
    if not ok2b:
        fails.append(f"名稱修正回退:{stale}")

    print("\n(3) 統一角色編號恆等(doc31):face_portrait 必須等於 index")
    with open(CHARACTERS_JSON, encoding="utf-8") as fh:
        chars = json.load(fh)
    bad = [c["index"] for c in chars if c["face_portrait"] != c["index"]]
    ok3 = len(chars) == 32 and not bad
    print(f"    {'PASS' if ok3 else 'FAIL'}: {len(chars)} 人,不恆等的 {bad}")
    if not ok3:
        fails.append(f"恆等假設不成立:{len(chars)} 人 / {bad}")

    print("\n(4) characters.json 沒有的通用組必須在合併後仍在")
    lost = [g for g in EXTRA_NAMES if names.get(g) != EXTRA_NAMES[g]]
    json_ids = {c["index"] for c in chars}
    overlap = sorted(set(EXTRA_NAMES) & json_ids)
    ok4 = not lost and not overlap
    print(f"    {'PASS' if ok4 else 'FAIL'}: 遺失 {lost}、與 JSON 重疊 {overlap}")
    if not ok4:
        fails.append(f"通用組合併不正確:{lost} / {overlap}")

    print("\n(5) sprite 索引公式(doc31 反組譯 0x1291e:組×12+方向×3+幀)")
    cases = [((0, 0, 0), 0), ((1, 0, 0), 12), ((0, 1, 0), 3), ((0, 0, 2), 2),
             ((12, 0, 0), 144), ((139, 3, 2), 139 * 12 + 11)]
    wrongf = [(a, e, sprite_frame_index(*a)) for a, e in cases
              if sprite_frame_index(*a) != e]
    total_ok = GROUPS_DEFAULT * SPRITE_STRIDE == 1680
    ok5 = not wrongf and total_ok
    print(f"    {'PASS' if ok5 else 'FAIL'}: 6 例相符={not wrongf}、"
          f"140×12=1680(doc31 幀數)={total_ok}")
    if not ok5:
        fails.append(f"sprite 索引公式不符:{wrongf} / total={total_ok}")

    print("\n(6) 非平凡性 + 負向控制:有名/無名的標籤必須真的不同")
    labelled = character_label(30, names)      # 蓋亞,舊表沒有
    unknown = character_label(200, names)      # 沒有人的組號
    ok6 = (labelled == "30 蓋亞" and unknown == "200"
           and character_label(30, OLD_NAMES_0_21_BEFORE_2026_09_09) == "30")
    print(f"    {'PASS' if ok6 else 'FAIL'}: 新表 {labelled!r}、未知組 {unknown!r}、"
          f"舊表同一組 {character_label(30, OLD_NAMES_0_21_BEFORE_2026_09_09)!r}")
    if not ok6:
        fails.append(f"標籤行為不符:{labelled!r}/{unknown!r}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(缺口回歸 + 既有標籤不變 + 編號恆等 + 合併保全 "
          "+ 索引公式 + 非平凡性 + 權威名字表核對)。圖片組裝未涵蓋,見 docstring。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
