#!/usr/bin/env python3
"""炎龍騎士團2 — 一鍵全素材抽取(把原版資產解成現代格式,分類整齊輸出)。

把原版(玩家自備)的 FLAME2/ 解成:
    extracted/
      raw/<CONTAINER>/        .DAT 容器解包的原始 sub-resource
      images/                 標題 / 戰鬥背景等全幅圖 (PNG)
      animations/<RES>/*.png  FIGANI 戰鬥動畫逐幀 (PNG)
      animations/<RES>.gif    每個動畫的 GIF
      music/*.mid             XMIDI → 標準 MIDI
      fonts/atlas.png         自製 16×16 中文字型字模表
      exe_tables/*.json       FD2.EXE 內數值表
      INDEX.md                本次抽取清單

⚠ 輸出全為遊戲著作權內容(漢堂國際),僅供本機研究 / 重製,不散布、不入版控。

用法:
    python3 tools/extract_all.py <FLAME2目錄> <輸出目錄> [--anim-limit N]
    python3 tools/extract_all.py --selftest
"""
import sys
import os
import glob
import struct

sys.path.insert(0, os.path.dirname(__file__))
import unpack_dat
import decode_image
import decode_figani
import decode_text
import xmi2mid

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# 每個階段的最低產出。抽取跑完卻什麼都沒產出,是這支工具最該報錯的情況,而
# 原本它會照樣寫出一份寫著「0 個」的 INDEX.md 然後 rc=0——同 char_summary
# 2026-09-03 那筆「exit 0 但完全沒有輸出訊息」的類別,只是換到編排層。
# 值是「必須大於」的下限,不是期望值:填精確數字會讓這道檢查變成跟著資料漂移的
# 回歸測試,而這裡要擋的是「整個階段沒跑起來」。
STAGE_FLOOR = {"raw": 0, "images": 0, "animations": 0, "music": 0}


def stage_verdict(counts: dict[str, int], skipped: list[str]) -> tuple[bool, list[str]]:
    """(整體是否可接受, 問題描述)。把「有沒有真的產出東西」變成可測的判斷。"""
    problems = []
    for name, floor in STAGE_FLOOR.items():
        if counts.get(name, 0) <= floor:
            problems.append(f"{name}/ 產出 {counts.get(name, 0)} 個,階段等於沒跑起來")
    for s in skipped:
        problems.append(f"{s} 被例外略過")
    return (not problems), problems


def enough_args(argv: list[str]) -> bool:
    """CLI 至少要有 `<GAME目錄> <輸出目錄>` 兩個位置參數。

    2026-09-11 從 main() 抽出:selftest 只驗了「一個參數 -> rc=1」,`< 3` 改成 `< 4`
    (剛好兩個參數的正常用法也被當成用法錯誤)逃掉;而直接以兩個參數跑 main 會真的
    解包整個遊戲,不適合放進 selftest。
    """
    return len(argv) >= 3


def main(argv):
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest()
    if not enough_args(argv):
        print(__doc__); return 1
    G = argv[1]
    OUT = argv[2]
    anim_limit = None
    if "--anim-limit" in argv:
        anim_limit = int(argv[argv.index("--anim-limit") + 1])

    os.makedirs(OUT, exist_ok=True)
    raw = os.path.join(OUT, "raw")
    log = []
    skipped: list[str] = []

    # 1. 解包所有 .DAT 容器
    os.makedirs(raw, exist_ok=True)
    nres = 0
    for f in sorted(glob.glob(os.path.join(G, "*.DAT"))):
        try:
            nres += unpack_dat.unpack(f, raw)
        except unpack_dat.NotAContainer:
            pass
    log.append(f"raw/ : 解包 .DAT 容器,共 {nres} 個 sub-resource")

    palp = os.path.join(raw, "FDOTHER", "FDOTHER_000.bin")
    if not os.path.exists(palp):
        print("找不到調色盤 FDOTHER_000,中止"); return 2
    pal = decode_image.load_palette(palp)

    # 2. 圖像(全幅:title/bg/fdother 未壓縮與 RLE)
    imgdir = os.path.join(OUT, "images")
    os.makedirs(imgdir, exist_ok=True)
    nimg = 0
    for f in sorted(glob.glob(os.path.join(raw, "*", "*.bin"))):
        r = decode_image.decode_image(f)
        if r and r[2] is not None:
            w, h, idx, mode = r
            name = os.path.splitext(os.path.relpath(f, raw).replace(os.sep, "_"))[0]
            decode_image.save_png(w, h, idx, pal, os.path.join(imgdir, f"{name}.png"))
            nimg += 1
    log.append(f"images/ : {nimg} 張全幅圖(未壓縮 + RLE 背景/標題)")

    # 3. FIGANI 動畫逐幀 + GIF
    animdir = os.path.join(OUT, "animations")
    os.makedirs(animdir, exist_ok=True)
    nanim = nframe = 0
    figani = sorted(glob.glob(os.path.join(raw, "FIGANI", "*.bin")))
    if anim_limit:
        figani = figani[:anim_limit]
    for f in figani:
        d = open(f, "rb").read()
        if len(d) < 12:
            continue
        try:
            frames = decode_figani.parse_anim(d)
        except Exception:
            continue
        if not frames:
            continue
        base = os.path.splitext(os.path.basename(f))[0]
        decode_figani.cmd_frames(f, palp, os.path.join(animdir, base))
        decode_figani.cmd_gif(f, palp, os.path.join(animdir, base + ".gif"))
        nanim += 1
        nframe += len(frames)
    log.append(f"animations/ : {nanim} 個動畫,共 {nframe} 幀(PNG 序列 + GIF)")

    # 4. 音樂 XMIDI → MIDI
    musdir = os.path.join(OUT, "music")
    os.makedirs(musdir, exist_ok=True)
    nmid = 0
    for f in sorted(glob.glob(os.path.join(raw, "FDMUS", "*.bin"))):
        d = open(f, "rb").read()
        if d[:4] != b"FORM":
            continue
        base = os.path.splitext(os.path.basename(f))[0]
        r = xmi2mid.convert(d, os.path.join(musdir, base + ".mid"), verbose=False)
        nmid += len(r)
    log.append(f"music/ : {nmid} 首 MIDI(XMIDI 轉出)")

    # 5. 字型字模表
    fontdir = os.path.join(OUT, "fonts")
    os.makedirs(fontdir, exist_ok=True)
    fontres = os.path.join(raw, "FDOTHER", "FDOTHER_004.bin")
    if os.path.exists(fontres):
        decode_text.font_atlas(fontres, os.path.join(fontdir, "atlas.png"))
        log.append("fonts/ : atlas.png(1824 字模 16×16 自製字型)")

    # 6. 人物頭像(DATO)
    try:
        import decode_dato
        portdir = os.path.join(OUT, "portraits")
        np = 0
        for f in sorted(glob.glob(os.path.join(raw, "DATO", "*.bin"))):
            if decode_dato.frames(f):
                decode_dato.save(f, palp, portdir); np += 1
        log.append(f"portraits/ : {np} 個人物頭像(各 4 嘴型幀)")
    except Exception as e:
        log.append(f"portraits/ : 略過({e})")
        skipped.append("portraits/")

    # 7. 戰場地圖(FDFIELD + FDSHAP)
    try:
        import extract_maps
        mapdir = os.path.join(OUT, "maps")
        os.makedirs(mapdir, exist_ok=True)
        extract_maps.main(["extract_maps", raw, palp, mapdir])
        log.append(f"maps/ : 全部戰場地圖(FDFIELD×FDSHAP tileset)")
    except Exception as e:
        log.append(f"maps/ : 略過({e})")
        skipped.append("maps/")

    # 8. INDEX
    with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8") as fp:
        fp.write("# 炎龍騎士團2 — 抽取素材清單\n\n")
        fp.write("> 全為漢堂國際遊戲著作權內容,僅本機研究/重製用,不散布。\n\n")
        for line in log:
            fp.write(f"- {line}\n")
    print("\n".join(log))
    ok, problems = stage_verdict(
        {"raw": nres, "images": nimg, "animations": nanim, "music": nmid}, skipped)
    if not ok:
        print("\n抽取未完整完成:", file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        print(f"(清單仍寫到 {OUT}/INDEX.md 供對照)", file=sys.stderr)
        return 3
    print(f"\n完成 → {OUT}/INDEX.md")
    return 0


GAME_DIR = "org_game/炎龍騎士團/FLAME2"
# 實測:11 個 .DAT 容器全部解得開,解包後 extracted/raw/ 下正好 11 個目錄。
CONTAINERS = 11


def selftest() -> int:
    """驗編排層的判斷,不重跑整包抽取。

    **範圍限制是刻意的**:完整抽取要解 409 個 FIGANI 動畫並寫出 GIF,不適合放進
    每次都要跑的 selftest;這裡驗的是「跑完之後怎麼判斷成功」那一層,以及本工具
    對容器數的宣稱是否與現地資料相符。解包本身的新鮮度由
    verify_dat_extraction_freshness 擁有,不在這裡重做。
    """
    fails = []

    print("(1) 本次修的 bug:全部階段產出 0 也回報成功")
    # 原本 8 個階段跑完直接 return 0,即使每個計數都是 0——只會寫出一份寫著
    # 「0 個」的 INDEX.md。這是「exit 0 但什麼都沒做」在編排層的版本。
    zero_ok, zero_problems = stage_verdict({"raw": 0, "images": 0,
                                            "animations": 0, "music": 0}, [])
    real_ok, real_problems = stage_verdict({"raw": 1006, "images": 40,
                                            "animations": 409, "music": 21}, [])
    ok1 = (not zero_ok) and len(zero_problems) == 4 and real_ok and not real_problems
    print(f"    {'PASS' if ok1 else 'FAIL'}: 全 0 -> 不可接受({len(zero_problems)} 個問題)、"
          f"正常計數 -> 可接受={real_ok}")
    if not ok1:
        fails.append(f"階段判斷不成立:zero_ok={zero_ok} real_ok={real_ok}")

    print("\n(2) 單一階段掛掉也必須擋下來,不能只有全掛才算失敗")
    one_ok, one_problems = stage_verdict({"raw": 1006, "images": 0,
                                          "animations": 409, "music": 21}, [])
    ok2 = (not one_ok) and len(one_problems) == 1 and "images/" in one_problems[0]
    print(f"    {'PASS' if ok2 else 'FAIL'}: 只有 images 掛 -> 不可接受、"
          f"問題數 {len(one_problems)}(應 1)")
    if not ok2:
        fails.append(f"單階段失敗未被擋下:{one_problems}")

    print("\n(2b) 訊息裡回報的計數必須是**真的讀到的值**,不是後備預設值")
    # 目前唯一的呼叫端(main())一定會完整給滿 4 個 key,所以 `.get(name, 0)` 的
    # 後備值在實際使用中從未被走到 —— 但函式簽章沒有禁止呼叫端漏給某個 key,
    # 這是型別提示允許、也值得單獨驗證的防禦性行為:缺鍵時訊息要老實顯示 0,
    # 不能被之後任何字面值竄改影響。
    missing_key_ok, missing_key_problems = stage_verdict({"raw": 1006, "images": 40}, [])
    ok2b = (not missing_key_ok
           and any("animations/ 產出 0 個" in p for p in missing_key_problems)
           and any("music/ 產出 0 個" in p for p in missing_key_problems))
    print(f"    {'PASS' if ok2b else 'FAIL'}: 缺 animations/music 兩個 key -> "
          f"{missing_key_problems}")
    if not ok2b:
        fails.append(f"缺 key 時的回報計數不對:{missing_key_problems}")

    print("\n(3) 被例外略過的階段必須進入判斷,而不是只留一行日誌")
    # portraits/ 與 maps/ 是 try/except 包起來的,原本例外只變成一行
    # 「略過(...)」寫進 INDEX.md,整體照樣 rc=0。
    skip_ok, skip_problems = stage_verdict({"raw": 1006, "images": 40,
                                            "animations": 409, "music": 21},
                                           ["portraits/"])
    ok3 = (not skip_ok) and any("portraits/" in p for p in skip_problems)
    print(f"    {'PASS' if ok3 else 'FAIL'}: 有階段被略過 -> 不可接受、問題 {skip_problems}")
    if not ok3:
        fails.append(f"被略過的階段沒有進入判斷:{skip_problems}")

    print("\n(4) 容器數宣稱:.DAT 個數與解包後的目錄數必須相符")
    dats = sorted(glob.glob(os.path.join(GAME_DIR, "*.DAT")))
    dirs = [d for d in glob.glob("extracted/raw/*") if os.path.isdir(d)]
    ok4 = len(dats) == CONTAINERS and len(dirs) == CONTAINERS
    print(f"    {'PASS' if ok4 else 'FAIL'}: {len(dats)} 個 .DAT、"
          f"{len(dirs)} 個解包目錄(皆應 {CONTAINERS})")
    if not ok4:
        fails.append(f"容器數不符:.DAT {len(dats)}、目錄 {len(dirs)}")

    print("\n(5) 非平凡性 + 負向控制")
    # 判斷函式必須真的看計數,而不是永遠回同一個答案。
    verdicts = {stage_verdict({"raw": r, "images": 1, "animations": 1, "music": 1}, [])[0]
                for r in (0, 1, 999)}
    # enough_args 兩側:剛好兩個位置參數必須放行(`< 3` 改成 `< 4` 會把正常用法擋掉)。
    ok5 = (verdicts == {False, True} and main(["extract_all"]) == 1
           and enough_args(["extract_all", "GAME", "out"]) and not enough_args(["extract_all", "GAME"]))
    print(f"    {'PASS' if ok5 else 'FAIL'}: 不同計數給出不同判斷={verdicts}、"
          f"參數不足 -> rc=1")
    if not ok5:
        fails.append(f"判斷函式恆定或用法檢查失效:{verdicts}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(全 0 回報成功的回歸 + 單階段失敗 + 被略過的階段 "
          "+ 容器數宣稱 + 非平凡性與負向控制)。完整抽取未涵蓋,見 docstring。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
