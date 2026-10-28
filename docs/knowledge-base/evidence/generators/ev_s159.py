"""續一百五十九證據:evidence/copyprot_patch_record_s159_20261028.json(第 6 項:防拷兩處無條件跳躍是誰改的;
使用者 2026-10-28「第六項 若需要新建或優化工具 請自行解決 並 完整解決問題」)。

續一百三十七從位元組形狀推論兩處 EB 是編譯之後的修補,續一百三十八比過磁碟上三份 FD2 目錄都已含 EB,沒有未修改的版本可比。
這一輪找到 `FD2_APK/PASS.DAT`(1995-07-15):內容是 MS-DOS COMP 的輸出 —— 修補後的檔(file1)與一份未修改的檔(file2)只差兩個 byte。
(A) PASS.DAT 逐字解析成 COMP 的格式,兩筆差異的檔案位移以兩個獨立的 LE 換算(disasm_le.lin2file、le_xref.file_to_linear)
    對回 linear 位址;參考版在那兩處的 byte = file1。
(B) file2 套回參考版 = 未修改的原版:反組譯兩處是 jne / je,目標與 EB 相同(rel8 不變);續一百三十七反事實用的值(ev_s137.py 原始碼)
    與 file2 相同。COMP 不同大小的檔不比、10 筆差異就停,2 筆表示兩檔只差這兩個 byte。
(C) 三份目錄的快照(檔名、大小、修改時間、md5):原版資料檔的時間序、FD2.EXE 各份的時間、PASS.DAT / PLAY.BAT / SETUP.BAT 只在 FD2_APK;
    全 C 槽掃描找到的同大小檔都在快照裡,沒有一份是重建出的原版。
(D) 第 5 項第 5 次(lc159a,使用者 2026-10-28 核准):設定步驟(開「結束這回合?」框)沒有達成 —— 索爾移到上一格、行動結束;依規則停止。
全部從 FD2.EXE、.wsl_build/s159_copyprot/、.wsl_build/lc159_live/ 重算;任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402
import le_xref as lx  # noqa: E402

EXE_P = GAME / "FD2.EXE"
RAW = ROOT / ".wsl_build" / "s159_copyprot"
OUT = out_path("copyprot_patch_record_s159_20261028.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
APK_MD5 = "a6e341a8decc6ebf7f4872076d9cf161"   # FD2_APK/FD2.EXE(2004-10-23,續一百三十八)
SITES = (0x118AA, 0x34233)                      # 續三十六 / 續一百二十一 / 續一百三十七 的兩處 EB
COPYPROT = 0x33FAF                              # copy_protection_password_check

_D = EXE_P.read_bytes()
assert hashlib.md5(_D).hexdigest() == MD5
META = dl.parse_le(_D)
MD = dl._capstone()


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


# ================= (A) PASS.DAT = MS-DOS COMP 的輸出 =================
PASS = (RAW / "PASS.DAT").read_bytes()
_REC = re.compile(rb"Compare error at OFFSET ([0-9A-F]+)\r\nfile1 = ([0-9A-F]{2})\r\nfile2 = ([0-9A-F]{2})\r\n")
RECS = [(int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)) for m in _REC.finditer(PASS)]
# 逐字:整個檔案就是這幾筆記錄接起來,沒有其他內容(沒有署名、沒有說明)
assert b"".join(m.group(0) for m in _REC.finditer(PASS)) == PASS, PASS
assert len(RECS) == 2, RECS
assert len(RECS) < 10          # COMP 第 10 筆差異就停止比對;不到 10 筆 = 這就是全部的差異
OFFS = [o for o, _f1, _f2 in RECS]
assert len(_D) == 509158 and all(o < len(_D) for o in OFFS)   # COMP 只比同大小的檔

LIN = [lx.file_to_linear(META, o) for o in OFFS]
assert LIN == list(SITES), [hex(x) for x in LIN]
assert [dl.lin2file(META, a) for a in SITES] == OFFS             # 另一個換算方向 / 另一份實作
assert [o - a for o, a in zip(OFFS, SITES)] == [0x26014, 0x26014]
FILE1 = [_D[o] for o in OFFS]
assert FILE1 == [f1 for _o, f1, _f2 in RECS] == [0xEB, 0xEB]     # file1 = 參考版(修補後)
FILE2 = [f2 for _o, _f1, f2 in RECS]

# ================= (B) file2 = 未修改的原版 =================
ORIG = bytearray(_D)
for o, f2 in zip(OFFS, FILE2):
    ORIG[o] = f2
ORIG = bytes(ORIG)
ORIG_MD5, ORIG_SHA = md5(ORIG), hashlib.sha256(ORIG).hexdigest()
assert sum(a != b for a, b in zip(ORIG, _D)) == 2


def decode(buf: bytes, start: int, n: int) -> list[tuple[int, str, str]]:
    f = dl.lin2file(META, start)
    return [(i.address, i.mnemonic, i.op_str) for i in MD.disasm(buf[f:f + n], start)]


CTX = {0x118AA: (0x118A3, 16), 0x34233: (0x34231, 13)}
SEM = {}
for site in SITES:
    start, n = CTX[site]
    pat, org = decode(_D, start, n), decode(ORIG, start, n)
    assert [x[0] for x in pat] == [x[0] for x in org]           # 只換 opcode,指令邊界不變
    jp = next(x for x in pat if x[0] == site)
    jo = next(x for x in org if x[0] == site)
    assert jp[1] == "jmp" and jp[2] == jo[2], (jp, jo)          # rel8 位移不變,目標相同
    SEM[hex(site)] = {"patched": f"{jp[1]} {jp[2]}", "original": f"{jo[1]} {jo[2]}",
                      "context_original": [f"{a:#x} {m} {o}" for a, m, o in org]}
# 0x118a3:cmp byte [0x53a44], 0(檔案裡是未重定位值 0x3a44);原版 jne 跳過 call 防拷問答 —— 旗標仍是 0(還沒答對)時就問,
# 問完 jmp 回 0x118a3 再看旗標
assert SEM["0x118aa"]["context_original"] == [
    "0x118a3 cmp byte ptr [0x3a44], 0", "0x118aa jne 0x118b3", f"0x118ac call {COPYPROT:#x}", "0x118b1 jmp 0x118a3"], SEM
# 0x34231:cmp eax, ebx;原版 je 跳過「答錯」旗標 [esp + 0x34] = 1 —— 修補後永遠跳過,比對恆通過(續一百二十一)
assert SEM["0x34233"]["context_original"][:3] == [
    "0x34231 cmp eax, ebx", "0x34233 je 0x3421e", "0x34235 mov byte ptr [esp + 0x34], 1"], SEM
assert {k: (v["patched"], v["original"]) for k, v in SEM.items()} == {
    "0x118aa": ("jmp 0x118b3", "jne 0x118b3"), "0x34233": ("jmp 0x3421e", "je 0x3421e")}, SEM
assert [x[1] for x in decode(_D, 0x118AA, 2)] == ["jmp"] and [x[1] for x in decode(_D, 0x34233, 2)] == ["jmp"]

# 續一百三十七的反事實(2026-10-20,看到 PASS.DAT 之前)用的原 opcode,從 ev_s137.py 原始碼讀
_src = (GEN_DIR / "ev_s137.py").read_text(encoding="utf-8")
_m =re.findall(r"(0x[0-9A-F]+): \(.*?, (0x[0-9A-F]+), (0x[0-9A-F]+)\)", _src.split("PATCH = {", 1)[1].split("}", 1)[0])
S137 = {int(a, 16): int(v, 16) for a, _s, v in _m}
assert S137 == dict(zip(SITES, FILE2)) == {0x118AA: 0x75, 0x34233: 0x74}, S137

# ================= (C) 三份目錄的快照與全 C 槽掃描 =================
SNAP = json.loads((RAW / "dirs.json").read_text(encoding="utf-8"))
ROW = {(d, r["name"]): r for d in ("FD2", "FD2_USB", "FD2_APK") for r in SNAP[d]}
assert md5(PASS) == ROW[("FD2_APK", "PASS.DAT")]["md5"]
for n in ("PLAY.BAT", "SETUP.BAT"):
    assert md5((RAW / n).read_bytes()) == ROW[("FD2_APK", n)]["md5"]
assert (RAW / "PLAY.BAT").read_bytes() == b"fd2\r\n" and (RAW / "SETUP.BAT").read_bytes() == b"setsound\r\n"
EXES = {k: (r["md5"], r["mtime_local"]) for k, r in ROW.items() if r["name"].upper().endswith(".EXE") and r["size"] == len(_D)}
assert EXES == {("FD2", "FD2.EXE"): (MD5, EXES[("FD2", "FD2.EXE")][1]),
                ("FD2_USB", "FD2.EXE"): (MD5, "1995-07-07 14:52:16"),
                ("FD2_APK", "FD2_old.EXE"): (MD5, "1995-07-14 22:16:52"),
                ("FD2_APK", "FD2.EXE"): (APK_MD5, "2004-10-23 01:49:48")}, EXES
assert ORIG_MD5 not in {r["md5"] for r in ROW.values()}
# 只有 FD2_APK 有的發行檔:PASS.DAT、PLAY.BAT、SETUP.BAT(1995-07-15 早上兩分鐘內)、FD2_old.EXE
ONLY_APK = sorted(r["name"] for (d, _n), r in ROW.items() if d == "FD2_APK" and r["mtime_local"] < "2000"
                  and ("FD2", r["name"]) not in ROW and ("FD2_USB", r["name"]) not in ROW)
assert ONLY_APK == ["FD2_old.EXE", "PASS.DAT", "PLAY.BAT", "SETUP.BAT"], ONLY_APK
T = {n: ROW[("FD2_APK", n)]["mtime_local"] for n in ONLY_APK}
assert T["FD2_old.EXE"] < T["PASS.DAT"] < T["PLAY.BAT"] < T["SETUP.BAT"], T
assert T["PASS.DAT"][:10] == T["SETUP.BAT"][:10] == "1995-07-15"
# 三份共同的 1995 年檔逐一 md5 相同(同一套發行物),FD2.EXE 之外
DIRS = ("FD2", "FD2_USB", "FD2_APK")
USB95 = {r["name"] for (d, _n), r in ROW.items() if d == "FD2_USB" and r["mtime_local"] < "1996"} - {"FD2.EXE"}
COMMON = sorted(n for n in USB95 if all((d, n) in ROW and ROW[(d, n)]["mtime_local"] < "1996" for d in DIRS))
# 排除的只有 SETSOUND 寫的音效設定(FD2 / FD2_USB 是 1995-08-12,FD2_APK 是 2007 年重設)
assert sorted(USB95 - set(COMMON)) == ["DIG.INI", "MDI.INI"], sorted(USB95 - set(COMMON))
for n in COMMON:
    assert len({ROW[(d, n)]["md5"] for d in DIRS}) == 1, n
assert len(COMMON) == 42, len(COMMON)   # 27 個音效驅動 + 15 個遊戲檔
# 遊戲資料檔(.DAT / .B24)的時間序:FD2_USB 的 FD2.EXE 時間落在最後兩個資料檔之間,與開發過程的建置時間連續
DATA = sorted((r["mtime_local"], r["name"]) for (d, _n), r in ROW.items()
              if d == "FD2_USB" and r["name"].upper().endswith((".DAT", ".B24")) and r["mtime_local"] < "1996")
EXE_T = ROW[("FD2_USB", "FD2.EXE")]["mtime_local"]
before = [n for t, n in DATA if t < EXE_T]
after = [n for t, n in DATA if t > EXE_T]
assert after == ["FIGANI.DAT"] and before[-1] == "FDOTHER.DAT", (before, after)
FIRST_LAST = [DATA[0][0], DATA[-1][0]]
assert FIRST_LAST == ["1995-06-06 09:27:28", "1995-07-07 17:20:04"], FIRST_LAST
assert DATA[0][1] == "TAI.DAT" and DATA[-1][1] == "FIGANI.DAT"
# 全 C 槽掃描(PowerShell Get-ChildItem -Recurse,大小 509158 或檔名 PASS.DAT / FD2*.EXE / 封存檔):每一筆都在快照裡
SCAN = (RAW / "scan_c_drive.txt").read_text(encoding="utf-8-sig").splitlines()
assert SCAN[0].startswith("drives:") and SCAN[-1] == "done"
HITS = [ln.split("\t") for ln in SCAN[1:-1]]
assert all(len(h) == 3 for h in HITS) and len(HITS) == 5, HITS
for path, size, mt in HITS:
    d, n = path.split("\\")[-2:]
    r = ROW[(d, n)]
    assert int(size) == r["size"] and mt == r["mtime_local"], (path, r)
assert sorted(int(s) for _p, s, _t in HITS) == [110] + [len(_D)] * 4

# ================= (D) 第 5 項第 5 次(lc159a)在設定步驟 FAIL =================
# 找空格(Up 判為空格)→ Return → Down → Return 之後沒有「結束這回合?」框:Up 那格原本是草地,之後是灰階單位;下面一格(索爾原位)
# 原本有藍色的索爾、之後是草地 —— 索爾移到 Up 那格並且行動結束。截圖 1024 × 768(2 倍),兩張捲動相同。
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

SHOT = ROOT / ".wsl_build" / "lc159_live" / "lc159a" / "prompt"


def _rgb(n: str):
    im = Image.open(SHOT / n)
    assert im.size == (1024, 768) and im.mode == "P"
    return np.array(im.convert("RGB")).astype(np.int32)


def _cls(a, y0: int) -> dict[str, int]:
    b = a[y0:y0 + 38, 734:772]                     # 游標格 / 下一格的內側 38 × 38(避開游標框)
    sat = b.max(2) - b.min(2)
    return {"grey": int(((sat <= 12) & (b.max(2) > 40)).sum()),
            "green": int(((b[:, :, 1] > b[:, :, 0] + 15) & (b[:, :, 1] > b[:, :, 2] + 15)).sum()),
            "blue": int((b[:, :, 2] > b[:, :, 0] + 30).sum())}


def _consistency(a, b) -> float:
    """a 的每個顏色在 b 同位置最常對到的顏色所佔比例(兩張調色盤不同,逐像素相等不適用;同場景、同捲動 → 接近 1)。"""
    ka = (a[..., 0] << 16 | a[..., 1] << 8 | a[..., 2]).ravel().tolist()
    kb = (b[..., 0] << 16 | b[..., 1] << 8 | b[..., 2]).ravel().tolist()
    m: dict[int, Counter] = defaultdict(Counter)
    for x, y in zip(ka, kb):
        m[x][y] += 1
    return sum(c.most_common(1)[0][1] for c in m.values()) / len(ka)


UP, NOW = _rgb("findempty_001_Up.png"), _rgb("now1.png")
SCROLL_SAME = _consistency(UP[400:593, 488:680], NOW[400:593, 488:680])          # 教堂屋頂一帶
SCROLL_CTRL = (_consistency(UP[448:593, 488:680], NOW[400:545, 488:680]),        # 對照:錯一格(48 列 / 48 欄)
               _consistency(UP[400:593, 536:680], NOW[400:593, 488:632]))
assert SCROLL_SAME > 0.9 and max(SCROLL_CTRL) < 0.6, (SCROLL_SAME, SCROLL_CTRL)  # 兩張捲動相同
CELL_UP = {"before": _cls(UP, 262), "after": _cls(NOW, 262)}
CELL_SOL = {"before": _cls(UP, 310), "after": _cls(NOW, 310)}
assert CELL_UP["before"]["green"] > 2 * CELL_UP["before"]["grey"]       # Up 那格:草地
assert CELL_UP["after"]["grey"] > 20 * CELL_UP["after"]["green"]        # 之後:灰階單位(行動結束)
assert CELL_SOL["before"]["blue"] > 200 and CELL_SOL["after"]["blue"] == 0 and CELL_SOL["after"]["green"] > 700
# 量到的值釘住(上面是判準;這裡防止視窗 / 門檻被改了卻沒人發現)
assert CELL_UP == {"before": {"grey": 84, "green": 610, "blue": 148}, "after": {"grey": 1232, "green": 28, "blue": 0}}, CELL_UP
assert CELL_SOL == {"before": {"grey": 16, "green": 346, "blue": 358}, "after": {"grey": 148, "green": 1038, "blue": 0}}, CELL_SOL
SC_SAME, SC_CTRL = round(SCROLL_SAME, 4), [round(x, 4) for x in SCROLL_CTRL]
assert (SC_SAME, SC_CTRL) == (0.9325, [0.5289, 0.3685]), (SC_SAME, SC_CTRL)
ITEM5 = {"run": "lc159a", "verdict": "FAIL(設定步驟,未進入量測)", "cursor_tile": CELL_UP, "sol_tile": CELL_SOL,
         "scroll_consistency": SC_SAME, "scroll_controls": SC_CTRL,
         "predictions": "drivers_s159/pred159_item5.txt(P0 .. P5 NOT TESTED)"}

OUTD = {
    "generator": rel(GEN_DIR / "ev_s159.py"),
    "exe": {"path": rel(EXE_P), "md5": MD5},
    "pass_dat": {"path": ".wsl_build/s159_copyprot/PASS.DAT (copy of GAME/FD2_APK/PASS.DAT)", "bytes": len(PASS),
                 "format": "MS-DOS COMP:Compare error at OFFSET / file1 / file2", "records": [
                     {"offset": f"{o:#x}", "linear": f"{a:#x}", "file1": f"{f1:02x}", "file2": f"{f2:02x}"}
                     for (o, f1, f2), a in zip(RECS, LIN)],
                 "file_offset_minus_linear": "0x26014", "file1_is_reference_exe": True,
                 "only_these_two_bytes_differ": True},
    "original_reconstructed": {"md5": ORIG_MD5, "sha256": ORIG_SHA, "size": len(ORIG),
                               "on_disk": False, "semantics": SEM},
    "s137_counterfactual_opcodes": {f"{k:#x}": f"{v:02x}" for k, v in S137.items()},
    "timeline_local": {"data_files_first_last": FIRST_LAST, "FD2_USB/FD2.EXE": EXE_T,
                       "FD2_APK_only": T, "FD2_APK/FD2.EXE": EXES[("FD2_APK", "FD2.EXE")][1]},
    "common_1995_files_identical": len(COMMON),
    "scan_c_drive_hits": len(HITS),
    "item5_run5": ITEM5,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, ORIG_MD5)
