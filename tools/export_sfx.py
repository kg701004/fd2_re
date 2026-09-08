#!/usr/bin/env python3
"""炎龍騎士團2 (Flame Dragon Knight 2) SFX 導出工具。

FDOTHER.DAT 資源 #31 是巢狀 `LLLLLL` 容器(見 docs/knowledge-base/36-sfx-audio-data.md),
內含 14 個子樣本,格式為 8-bit unsigned mono raw PCM(無檔頭)。本工具解開巢狀容器,
逐個子樣本補上標準 44-byte RIFF/WAV 檔頭,輸出到 extracted/sfx/。

取樣率:反組譯未找到 AIL_set_sample_type/set_sample_playback_rate 立即數呼叫點
(見 docs/knowledge-base/36 待辦),沿用文件既有推定值 11025Hz ── 1995 年 AIL 遊戲常見預設值。

第 10 輪新增 `--battle` 模式:戰鬥音效走另一批 FDOTHER.DAT 子資源；其中
`#48/#49/#50/#51/#52/#53/#64/#78/#88` 是動態候選池，`#95` 是 0x32999
第 1 次呈現直接使用的固定資源（見 docs/knowledge-base/36），
用同一個巢狀 LLLLLL 解包邏輯,輸出到 extracted/sfx/battle_<資源號>_<子序>.wav。

第 12 輪新增 `--actionid` 模式:玩家選定的物理攻擊類指令(action_id 0-9)經
`FUN_0002ff01`(linear 0x2ff01)動態載入的真實 SFX 池家族 `#82-90`(見 doc36 第12輪,
Ghidra headless 反組譯+ decompile 動態追出,逐一驗證為合法 LLLLLL 容器),輸出到
extracted/sfx/actionid_<資源號>_<子序>.wav。與 `--battle` 家族相鄰但不同,僅 #88 重疊。

用法:
    python3 tools/export_sfx.py                # UI 音效池(資源 #31)→ sfx_NN.wav
    python3 tools/export_sfx.py --battle        # 戰鬥音效候選家族(第10輪) → battle_NN_MM.wav
    python3 tools/export_sfx.py --actionid      # action_id 0-9 真實家族(第12輪) → actionid_NN_MM.wav
    python3 tools/export_sfx.py --res <idx>      # 導出任意 FDOTHER.DAT 資源號(需為巢狀容器)
"""
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(__file__))
from unpack_dat import parse_directory, NotAContainer

FDOTHER_DAT = os.path.join(
    os.path.dirname(__file__), "..", "org_game", "炎龍騎士團", "FLAME2", "FDOTHER.DAT")
# 2026-09-03 全工具驗證修正:原本寫 extracted/FDOTHER/,但 unpack_dat.py 產出的
# (也是 repo 裡實際存在的)路徑是 extracted/raw/FDOTHER/,所以這支工具從來沒辦法
# 用預設路徑跑起來,一執行就 FileNotFoundError。
SRC = os.path.join(os.path.dirname(__file__), "..", "extracted", "raw", "FDOTHER", "FDOTHER_031.bin")
# 2026-09-03:輸出目錄從 remake/assets/sfx 改成 extracted/sfx。remake/ 已於
# 2026-09-02 依使用者指示整個移除,而本工具會自己 makedirs,實測會把 remake/
# 樹重新長回來(本次驗證就發生過,已刪除)。extracted/ 本來就是本 repo 放
# 原版衍生資產的地方,且已被 .gitignore 排除。
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "extracted", "sfx")
SAMPLE_RATE = 11025  # 推定值,見 docs/knowledge-base/36-sfx-audio-data.md 待辦

# 戰鬥音效候選池:PCM 特徵(值集中 0x80 附近、std 窄)比對確認,見 doc36 第 10 輪。
# 精確「哪個 index 對應哪招」仍是動態值(攻擊資料決定),此處先把整個候選家族導出。
BATTLE_EXPORT_INDICES = [48, 49, 50, 51, 52, 53, 64, 78, 88, 95]

# 第 12 輪動態追出的真實家族:action_id 0-9(玩家選定的物理攻擊類指令,見 doc36
# 第 12 輪)經 FUN_0002ff01(0x2ff01)用 linear 0x0526bc 起的全域表動態載入,
# 逐一解包驗證皆為合法巢狀 LLLLLL PCM 容器,sub0 逐位元組相同(共用揮擊音)。
# 與 BATTLE_EXPORT_INDICES 的候選家族(#48-53/64/78)是相鄰但不同的家族,僅 #88 重疊。
BATTLE_ACTION_ID_INDICES = [82, 83, 84, 85, 86, 87, 88, 89, 90]


def selftest():
    """把註解裡兩個**已記錄的 RE 結論**變成每次重跑的檢查。

    第 12 輪記載:action_id 0-9 對應 FDOTHER.DAT 的 #82-90,「逐一解包驗證皆為
    合法巢狀 LLLLLL PCM 容器,sub0 逐位元組相同(共用揮擊音)」。那是可驗證的,
    而且一旦哪天索引或容器結構被改動,結論會安靜失效。

    第 (2) 題是**負向對照**:候選家族 BATTLE_EXPORT_INDICES 與 action_id 家族
    「相鄰但不同,僅 #88 重疊」—— 那個重疊關係本身也是結論的一部分。

    另外釘住一個已知的路徑地雷:SRC 指向 `extracted/raw/FDOTHER/...`,而索引常數
    是對 **FDOTHER.DAT 頂層**(104 個子資源)的。兩者容器不同,拿 SRC 去套索引會
    IndexError —— 我在寫這個 selftest 時就先踩了一次。
    """
    import hashlib
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    if not os.path.isfile(FDOTHER_DAT):
        print("SKIP: 找不到 org_game 的 FDOTHER.DAT")
        return 0
    dat = open(FDOTHER_DAT, "rb").read()
    entries = parse_directory(dat)

    print("(1) 回歸:action_id 家族 #82-90 全部是合法巢狀容器,且 sub0 逐位元組相同")
    digests, nested = set(), 0
    for i in BATTLE_ACTION_ID_INDICES:
        if i >= len(entries):
            fails.append(f"索引 #{i} 超出 FDOTHER.DAT 的 {len(entries)} 個子資源")
            continue
        off, ln = entries[i]
        blob = dat[off:off + ln]
        try:
            inner = parse_directory(blob)
        except NotAContainer:
            continue
        nested += 1
        s0, l0 = inner[0]
        digests.add(hashlib.md5(blob[s0:s0 + l0]).hexdigest())
    ok1 = nested == len(BATTLE_ACTION_ID_INDICES) and len(digests) == 1
    print(f"    {'PASS' if ok1 else 'FAIL'}: 巢狀容器 {nested}/"
          f"{len(BATTLE_ACTION_ID_INDICES)}、sub0 相異雜湊 {len(digests)}(應為 1)")
    if not ok1:
        fails.append(f"action_id 家族不符記載:巢狀 {nested}、相異 sub0 {len(digests)}")

    print("\n(2) 兩個家族的關係:相鄰但不同,交集必須恰好是 {88}")
    overlap = set(BATTLE_EXPORT_INDICES) & set(BATTLE_ACTION_ID_INDICES)
    ok2 = overlap == {88}
    print(f"    {'PASS' if ok2 else 'FAIL'}: 交集 {sorted(overlap)}(應為 [88])")
    if not ok2:
        fails.append(f"兩個家族的交集是 {sorted(overlap)},與記載不符")

    print("\n(3) 路徑地雷:索引常數是對 FDOTHER.DAT 頂層,不是對 SRC 那個子資源")
    src_n = 0
    if os.path.isfile(SRC):
        try:
            src_n = len(parse_directory(open(SRC, "rb").read()))
        except NotAContainer:
            src_n = -1
    ok3 = src_n >= 0 and max(BATTLE_ACTION_ID_INDICES) >= src_n \
        and max(BATTLE_ACTION_ID_INDICES) < len(entries)
    print(f"    {'PASS' if ok3 else 'FAIL'}: SRC 有 {src_n} 個子資源、"
          f"FDOTHER.DAT 有 {len(entries)} 個;最大索引 "
          f"{max(BATTLE_ACTION_ID_INDICES)} 只在後者範圍內")
    if not ok3:
        fails.append("索引與容器的對應關係與預期不符")

    print("\n(4) export_container 對非容器必須回空清單而不是崩(它自己這樣宣告)")
    got = export_container(b"not a container" * 4, "zz_", "selftest")
    ok4 = got == []
    print(f"    {'PASS' if ok4 else 'FAIL'}: 回傳 {got}")
    if not ok4:
        fails.append(f"非容器輸入回傳 {got}")

    print("\n(5) 非恆真控制:不同家族外的索引,其 sub0 不應等於揮擊音")
    other = None
    for i in range(len(entries)):
        if i in BATTLE_ACTION_ID_INDICES:
            continue
        off, ln = entries[i]
        blob = dat[off:off + ln]
        try:
            inner = parse_directory(blob)
        except NotAContainer:
            continue
        s0, l0 = inner[0]
        h = hashlib.md5(blob[s0:s0 + l0]).hexdigest()
        if h not in digests:
            other = (i, h[:10])
            break
    ok5 = other is not None
    print(f"    {'PASS' if ok5 else 'FAIL'}: 家族外找到 sub0 不同的資源 {other}"
          f"(找不到就代表這個雜湊比對沒有鑑別力)")
    if not ok5:
        fails.append("所有巢狀容器的 sub0 都相同 —— 第 (1) 題的比對沒有鑑別力")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(action_id 家族回歸 + 家族交集 + 容器/索引對應 + "
          "非容器處理 + 非恆真控制)。")
    return 0


def export_container(data: bytes, name_prefix: str, label: str):
    try:
        entries = parse_directory(data)
    except NotAContainer as e:
        print(f"  [{label}] 不是合法的 LLLLLL 容器,略過: {e}")
        return []

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"[{label}] {len(data)} bytes, {len(entries)} 個子樣本")

    written = []
    for i, (off, ln) in enumerate(entries):
        pcm = data[off:off + ln]
        if len(pcm) == 0:
            print(f"  {name_prefix}{i:02d}: 0 bytes(目錄結尾哨兵),略過")
            continue
        out_path = os.path.join(OUT_DIR, f"{name_prefix}{i:02d}.wav")
        with wave.open(out_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)  # 8-bit unsigned
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm)
        dur_ms = len(pcm) / SAMPLE_RATE * 1000
        print(f"  {name_prefix}{i:02d}: {len(pcm):6d} bytes -> {dur_ms:7.1f} ms  ({out_path})")
        written.append(out_path)
    return written


def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--selftest':
        return selftest()
    argv = sys.argv[1:]

    if "--battle" in argv or "--res" in argv or "--actionid" in argv:
        dat = open(FDOTHER_DAT, "rb").read()
        try:
            top_entries = parse_directory(dat)
        except NotAContainer as e:
            print(f"錯誤: {FDOTHER_DAT} 不是合法的 LLLLLL 容器: {e}")
            return 1

        if "--res" in argv:
            idx = int(argv[argv.index("--res") + 1])
            indices = [idx]
            prefix = "battle_"
        elif "--actionid" in argv:
            indices = BATTLE_ACTION_ID_INDICES
            prefix = "actionid_"
        else:
            indices = BATTLE_EXPORT_INDICES
            prefix = "battle_"

        written = []
        for idx in indices:
            off, ln = top_entries[idx]
            chunk = dat[off:off + ln]
            written += export_container(chunk, f"{prefix}{idx:02d}_", f"FDOTHER.DAT #{idx}")

        print(f"\n完成: {len(written)} 個 WAV 已寫入 {OUT_DIR}")
        return 0

    data = open(SRC, "rb").read()
    written = export_container(data, "sfx_", os.path.basename(SRC))
    print(f"\n完成: {len(written)} 個 WAV 已寫入 {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
