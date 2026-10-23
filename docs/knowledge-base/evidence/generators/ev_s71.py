"""續七十一證據:evidence/offmap_event0_followups_20261002.json(續七十的四個未驗證項目)。

A. 亂碼對白:第 25 章 FDTXT_025 只有 8 條,事件 0 的第 0xb 條讀到偏移表之外(靜態 + v9a 斷點 + 執行期緩衝區重算)。
B. 名冊重複存檔:記錄戰況(v9a 戰中)、戰後寫回 0x11506(v9a)、酒店存檔槽(v9a)。
C. 地圖外的說話者:v9c(游標在地圖內 → 卡住)、v9b t1(游標已在地圖外 → 返回,對照)。
D. 名冊滿:v9b 把名冊補到 32 再觸發事件 0;記錄戰況、戰後寫回、酒店存檔、v9d 全新實例讀檔。
E. 靜態:誰寫名冊人數 [0x53bfb];名冊配置大小;正常流程的加入次數。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
SCR = GEN_DIR
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(SCR))
import fd2save as F  # noqa: E402
from sim_dialog import simulate  # noqa: E402

EXE = GAME / "FD2.EXE"
RAW = ROOT / "extracted/raw"
A_, B_, C_, D_ = (ROOT / f".wsl_build/ctr/{v}/ch25" for v in ("v9a", "v9b", "v9c", "v9d"))
D_ = ROOT / ".wsl_build/ctr/v9d"
OUT = out_path("offmap_event0_followups_20261002.json")
ROSTER = 0x1FC6C0


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def log_stops(path: Path) -> list[dict]:
    """驅動 log(每個停點一行,JSON 可能在 400 字被截斷):取 eip 與常用欄位。"""
    keys = ["eip", "kind", "off", "code4", "idx", "table", "ret", "x", "y", "flag", "xy", "cursor", "scroll",
            "event_id", "join_id", "count", "u16_before", "u16_after", "0x53c67", "0x53a79", "unit", "unit_xy",
            "pending_before", "pending_after", "esi"]
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(?P<key>\S+) (?P<rec>\{.*)", line)
        if not m:
            continue
        s, rec = m["rec"], {"key": m["key"]}
        for k in keys:
            mm = re.search(r'"%s": ("[^"]*"|\[[^\]]*\]|-?\d+)' % re.escape(k), s)
            if mm:
                rec[k] = json.loads(mm.group(1))
        out.append(rec)
    return out


RUNTIME_FIELDS = ("turn_counter", "runtime_count", "chapter", "camera_x", "camera_y", "cursor_x", "cursor_y",
                  "visible_cursor_x", "visible_cursor_y", "persistent_count")


def runtime(plain: bytes) -> dict[str, int]:
    """存檔明文 +0x30c3 起的執行期標頭(0x10010 讀檔時還原)。"""
    return dict(zip(RUNTIME_FIELDS, plain[F.CURRENT_RUNTIME_OFFSET:F.CURRENT_RUNTIME_OFFSET + len(RUNTIME_FIELDS)]))


def slot_meta(plain: bytes, slot: int = 0) -> tuple[int, int]:
    """存檔槽名冊之後的中繼資料:(章節 byte, 名冊人數 byte)。"""
    s, _ = F.slot_bounds(slot)
    chapter, count, *_ = plain[s + F.ROSTER_SIZE:s + F.SLOT_SIZE]
    return chapter, count


def records(buf: bytes) -> list[bytes]:
    """把一段名冊切成 0x50 的紀錄(長度必須是整數筆)。"""
    assert len(buf) % F.UNIT_SIZE == 0, len(buf)
    return [buf[i:i + F.UNIT_SIZE] for i in range(0, len(buf), F.UNIT_SIZE)]


def char_ids(recs: list[bytes]) -> list[int]:
    return [r[F.UNIT_CHARACTER_ID_OFFSET] for r in recs]


def join_fields_match(rec: bytes, char_id: int) -> bool:
    """rec 的 +5..+8 是 0x112a5 對新紀錄的固定寫入值:+5 = 0、+6 = 2、+7 = +8 = char_id(靜態反組譯)。"""
    return list(rec[5:9]) == [0, 2, char_id, char_id]


def text_entries(f: bytes) -> int:
    """FDTXT 偏移表的項數:第一個字 = 表的 byte 數(第一條字串緊接在表後);每項的起點都在檔內且遞增。"""
    first = struct.unpack_from("<H", f, 0)[0]
    n = first // 2
    assert 2 * n == first, first
    starts = [struct.unpack_from("<h", f, 2 * k)[0] for k in range(n)]  # 0x15fb9:esi = 表首 + word[idx]
    assert starts == sorted(starts) and starts[0] == first and starts[-1] < len(f), starts
    return n


def stops_json(path: Path) -> list[dict]:
    return [s for step in json.loads(path.read_text(encoding="utf-8")) for s in step["stops"]]


ev: dict = {"_meta": {
    "exe": rel(EXE), "exe_md5": md5(EXE),
    "chapter": "第 25 章戰場 = map 24(來源存檔 source_ch27.SAV 經 prepare_chapter_save,單位設定同續六十八~七十)",
    "raw_dirs": [".wsl_build/ctr/v9a/ch25", ".wsl_build/ctr/v9b/ch25", ".wsl_build/ctr/v9c/ch25", ".wsl_build/ctr/v9d"],
    "drivers": "evidence/generators/:t_v9.py / v9_setup.py / sim_dialog.py(本檔由 ev_s71.py 從原始紀錄重算)"}}
assert ev["_meta"]["exe_md5"] == "33464c81e6a364fd0660141139aa8e6e"

# ---------------- A ----------------
f25 = (RAW / "FDTXT/FDTXT_025.bin").read_bytes()
f01 = (RAW / "FDTXT/FDTXT_001.bin").read_bytes()
_font = (RAW / "FDOTHER/FDOTHER_004.bin").read_bytes()
GLYPH = 16 * 16 // 8  # 16×16、每像素 1 bit(0x4ed7a:font + glyph*32)
assert len(_font) % GLYPH == 0, len(_font)
font_n = len(_font) // GLYPH
_dump_p = A_ / "t1_txt_239494.bin"
TXT_BASE = int(_dump_p.stem.rsplit("_", 1)[1], 16)  # 傾印檔名 = 執行期緩衝區位址
dump = _dump_p.read_bytes()
matches = [n for n in range(35) if (g := (RAW / f"FDTXT/FDTXT_{n:03d}.bin").read_bytes()) and dump[:len(g)] == g]
assert matches == [25], matches
n01, n25 = text_entries(f01), text_entries(f25)
la = log_stops(A_ / "t1.log")
# 事件 0 讀的那條 = 實機 0x15f84 停點裡索引超出 FDTXT_025 偏移表的一筆(只有一筆)
_over = [i for i, s in enumerate(la) if s.get("eip") == "0x15f84" and s.get("idx", -1) >= n25]
assert len(_over) == 1, _over
i0, = _over
IDX = la[i0]["idx"]
assert IDX == 11 < n01, IDX  # 第 1 章的同一索引在表內,作對照
s_dump11, s_dump3 = simulate(dump, IDX, font_n), simulate(dump, 3, font_n)
s_file11, s_ch1 = simulate(f25, IDX, font_n), simulate(f01, IDX, font_n)
assert s_file11["table_word_offset"] == 2 * IDX, s_file11["table_word_offset"]
# 0x15f84(idx 11) 之後到第一個 end 之間的停點(dlg 模式斷了全部 10 個控制碼分支)
seg = []
for s in la[i0 + 1:]:
    seg.append(s)
    if s.get("kind") == "end":
        break
assert [x.get("kind") for x in seg] == ["end"] and seg[0]["off"] == s_dump11["events"][-1]["off"] == 11109
j0 = next(i for i, s in enumerate(la) if s.get("eip") == "0x15f84" and s.get("idx") == 3)
live3 = []
for s in la[j0 + 1:]:
    if "kind" in s:
        live3.append([s["kind"], s["off"]])
        if s["kind"] == "end":
            break
sim3 = [[e["kind"], e["off"]] for e in s_dump3["events"]]
assert live3 == sim3, (live3, sim3)
ev["A_garbled_dialog"] = {
    "static": {
        "player": "0x15f84(dialog):0x15fb9 movsx eax, word [esi + idx*2]; add esi, eax —— 不檢查 idx 是否小於偏移表項數",
        "glyph_draw": "非控制碼的字碼一律交給 0x4ed7a(draw_glyph16):font + glyph*32,沒有範圍檢查;bg 非 0 先把 16×16 填成 bg",
        "box_state": "[0x53c67] = 0(沒有開框碼)時字模從引數 3(0xa0000,螢幕左上角)開始畫,每字 +0x10",
        "control_codes": "-1 結束、-2 換行、-3 換頁、-4/-5 巢狀、-6 數字、-0x11/-0x12 以角色 id 開框、-0x13/-0x14 以單位索引開框;其餘都當字模"},
    "files": {"FDTXT_001_entries": n01, "FDTXT_025_entries": n25,
              "FDTXT_025_len": len(f25), "font_glyphs_FDOTHER_004": font_n},
    "ch1_control_idx11": {"start": s_ch1["start"], "events": s_ch1["events"], "text": "哈諾:『老爸!老爸!』(decode_story_text)"},
    "ch25_idx11_static": {"table_word_offset": s_file11["table_word_offset"], "start": s_file11["start"], "start_odd": s_file11["start_odd"],
                          "codes_until_file_end": s_file11["events"][-1]["glyphs_before"],
                          "control_codes_in_file": sum(e["kind"] != "past_file" for e in s_file11["events"])},
    "live_v9a": {"dialog_entry": {k: la[i0][k] for k in ("ret", "table", "idx", "0x53c67", "0x53a79")},
                 "runtime_buffer_equals": "FDTXT_025(3350 bytes 全同;FDTXT_034 是 0 byte,不計)",
                 "stops_between_entry_and_end": seg, "idx3_control_stops": live3},
    "recompute_on_runtime_dump": {"idx11": {k: s_dump11[k] for k in ("start", "codes_walked", "negative_glyph_codes")}
                                  | {"events": s_dump11["events"]},
                                  "idx3_events": sim3, "match_live": True},
    "portrait": "畫面左上的索爾頭像不是這條字碼流畫的(入口到結束之間 0 個控制碼停點);來源未追",
}

# ---------------- B ----------------
sb, sa = F.decode((A_ / "sav_before.SAV").read_bytes()), F.decode((A_ / "sav_after.SAV").read_bytes())
memr = (A_ / "mem_roster_at_save.bin").read_bytes()
R, M = F.CURRENT_PERSISTENT_ROSTER_OFFSET, F.CURRENT_RUNTIME_OFFSET
changed = [i for i in range(len(sa)) if sa[i] != sb[i]]
assert all(i < F.SLOT_OFFSET or i >= F.CHECKSUM_OFFSET for i in changed)
w2 = stops_json(A_ / "w2.json")
copies = [[s["unit_idx"], s["roster_idx"], s["unit_+7_+8"]] for s in w2 if s["eip"] == "0x11572"]
assert [4, 4, [33, 1]] in copies and [4, 16, [33, 1]] in copies
tb, ta = F.decode((A_ / "tav_before.SAV").read_bytes()), F.decode((A_ / "tav_after.SAV").read_bytes())
town = (A_ / "roster_town.bin").read_bytes()
o = F.SLOT_OFFSET
slot_after = ta[o:o + F.ROSTER_SIZE]
rt_a, rt_b = runtime(sa), runtime(sb)
snap = records(sa[R:R + F.ROSTER_SIZE])
snap_ids = char_ids(snap)[:rt_a["persistent_count"]]
*_, snap_new = snap[:rt_a["persistent_count"]]
(ch_b, cnt_b), (ch_a, cnt_a) = slot_meta(tb), slot_meta(ta)
slot_ids = F.roster_character_ids(ta, 0, cnt_a)
s_recs = records(slot_after)
hano = [i for i, c in enumerate(char_ids(s_recs)[:cnt_a]) if c == 1]
assert hano == [4, 16], hano
s_r4, s_r16 = (s_recs[i] for i in hano)
# 戰中事件 0 的 join(1):快照人數 = 戰前存檔人數 + 1,第 17 筆 = 新的哈諾(+7 = +8 = 1,0x112a5 的寫入值)
assert rt_a["persistent_count"] == cnt_b + 1 and snap_ids[-1] == 1 and join_fields_match(snap_new, 1), (rt_a, cnt_b)
# 戰後 0x24df2:JOIN(26) → 0x11506 → JOIN(29);0x11506 把戰場單位 #4(+7/+8 = 33/1)寫回兩筆哈諾
assert slot_ids == snap_ids + [26, 29] and ch_a == ch_b + 1, (slot_ids, ch_b, ch_a)
assert [list(s_r4[7:9]), list(s_r16[7:9])] == [c[2] for c in copies if c[1] in hano] == [[33, 1], [33, 1]], copies
ev["B_duplicate_persists"] = {
    "battle_save_v9a": {
        "path": "系統選單第 0 項 → 子選單 0x19df7 第 1 項 → 文字 0x19a「要記錄戰況嗎?」→ YES",
        "static": "0x19ffd..0x1a0b0:0xa00 bytes 名冊 [0x53bf7] 拷到 buffer +0x8a3,[0x53bfb] 的低 byte 存到 +0x30c3+9",
        "changed_bytes": len(changed),
        "changed_outside_0..0x312b_and_checksum": sum(F.SLOT_OFFSET <= i < F.CHECKSUM_OFFSET for i in changed),
        "snapshot_count_byte": rt_a["persistent_count"], "snapshot_roster_equals_memory": b"".join(snap) == memr,
        "snapshot_char_ids": snap_ids,
        "rec16_portrait_+7": snap_new[7], "before_snapshot_count_chapter": [rt_b["persistent_count"], rt_b["chapter"]]},
    "writeback_v9a": {
        "static": "0x11506(sync_party):對每個戰場單位逐筆比對名冊 +8,相同就 memcpy 0x50(0x11572)後 jmp 0x1153b 繼續比下一筆,不跳出",
        "post_handler": "0x24df2(第 25 章戰後):JOIN(26) → 0x11506 → JOIN(29)",
        "copies_unit_roster_+7+8": copies},
    "tavern_save_v9a": {
        "path": "戰後進城鎮酒店 → 「還有事嗎?」第 1 個圖示(存檔)→ 第 1 槽",
        "slot0_before": {"chapter": ch_b, "count": cnt_b},
        "slot0_after": {"chapter": ch_a, "count": cnt_a,
                        "char_ids": slot_ids},
        "slot_roster_equals_memory": slot_after[:len(town)] == town,
        "rec4_equals_rec16": s_r4 == s_r16,
        "rec16_hex": s_r16.hex()},
}

# ---------------- C ----------------
lc = log_stops(C_ / "t1.log")
trig = next(s for s in lc if s.get("pending_after") == "0x0")
cam = [s for s in lc if s.get("eip") in ("0x1636c", "0x165ac", "0x12cea", "0x165db") and lc.index(s) > lc.index(trig)]
hang = json.loads((C_ / "hang.json").read_text(encoding="utf-8"))
assert all(x["esi"] == 40 and x["cursor"] == [24, 14] and x["eip"] == "0x12d3b" for x in hang["xloop"])
lb = log_stops(B_ / "t1.log")
ctl = [s for s in lb if s.get("eip") in ("0x1636c", "0x165ac", "0x12cea", "0x165db")]
open_off = cam[0]["esi"] - TXT_BASE
assert struct.unpack_from("<h", dump, open_off)[0] in (-0x13, -0x14), open_off  # 0xFFED / 0xFFEC:以單位索引開框
ev["C_offmap_speaker"] = {
    "static": {"0xFFEC/0xFFED": "運算元是單位索引,直接取 [0x53a45]+索引*0x50 的 +0/+1,旗標 0x70/2 → 0x165ac 一定呼叫 camera_step_to",
               "0xFFEF/0xFFEE": "運算元是角色 id,0x12c60 在戰場找到活著的才回索引(旗標 2/0x70 → 移鏡頭);找不到回 -1(旗標 0 → 不移鏡頭),"
                                "此時 [0x53c1b] 是名冊裡最後一筆同 id 的紀錄,名冊也沒有就是 0(頭像讀 [0+7])",
               "clamp": "cursor_step_right / down 在 W−1 / H−1 不再加;left / up 在 0 不再減。座標是無號 byte,所以只有往右、往下越界會卡"},
    "test_v9c": {"trigger": trig, "after_trigger": cam, "open_code_off_rel_0x239494": open_off, "hang_samples": hang["samples"], "x_loop_stops": hang["xloop"],
                 "return_points_0x165db_0x12dab_hit": False},
    "control_v9b_t1": {"stops": ctl,
                       "note": "游標跟著走出地圖的單位 C 已在 x = 171,往左走到 40 不會被夾住,camera_step_to 返回(0x165db 停點)"},
}

# ---------------- D ----------------
f1 = stops_json(B_ / "f1.json")
jn = next(s for s in f1 if s["eip"] == "0x112a5" and s.get("ret") == "0x34543")
af = next(s for s in f1 if s["eip"] == "0x34543")
tb_ = bytes.fromhex(jn["tail_before"])
ta_ = bytes.fromhex(af["tail_after"])
FIRST_KEY = "rec32_first16"  # 名冊之後的前 N bytes(N 取自鍵名)
U = F.UNIT_SIZE  # tail_before / after 從名冊最後一筆(第 32 筆)開始
HEAP_HDR = bytes.fromhex("05030000")
ch = [i - U for i in range(len(ta_)) if ta_[i] != tb_[i]]
pal = (B_ / "pal_before_full.bin").read_bytes()
assert tb_[U:U + 4] == ta_[U:U + 4] == HEAP_HDR and tb_[U + 4:] == pal[4:4 + len(tb_) - U - 4]
assert ch and min(ch) >= 0 and max(ch) < U and join_fields_match(ta_[U:2 * U], 1), ch  # 只改第 33 筆的範圍
s33 = F.decode((B_ / "sav33_after.SAV").read_bytes())
m33 = (B_ / "mem_roster33.bin").read_bytes()
w1b = stops_json(B_ / "w1.json")
cp = [[s["unit_idx"], s["roster_idx"], s["hdr_after_roster"]] for s in w1b if s["eip"] == "0x11572"]
# 0x11572 停在 memcpy 之前,讀到的是「這次複製前」的標頭:第一個讀到新值的停點的前一筆就是寫壞標頭的那次複製
k_hdr = next(i for i, c in enumerate(cp) if c[2] != "05030000")
hdr_change = {"copy_that_wrote_it": cp[k_hdr - 1][:2], "first_stop_seeing_new_header": cp[k_hdr]}
assert hdr_change["copy_that_wrote_it"] == [4, 32]
t35 = F.decode((B_ / "tav35_after.SAV").read_bytes())
m35 = (B_ / "roster35.bin").read_bytes()
fresh = (D_ / "roster_fresh.bin").read_bytes()
rt33 = runtime(s33)
r35, r_fresh = records(m35), records(fresh)
ids35 = char_ids(r35)
ch35, cnt35 = slot_meta(t35)
# 記錄戰況的人數 = join 後的實機人數(33);戰後兩次 JOIN(26、29)→ 35 筆,第 33..35 筆 = 1、26、29
assert rt33["persistent_count"] == af["roster"]["count"] == 33 and cnt35 == len(r35) == 35, (rt33, cnt35, len(r35))
assert ids35[F.ROSTER_UNITS:] == [1, 26, 29] and ch35 == ch_a, (ids35, ch35)
# 全新實例讀檔:前 32 筆 = 存檔槽的 32 筆;名冊之後同樣是 0x305 區塊的標頭(新配置,與戰中相同的排列)
assert char_ids(r_fresh)[:F.ROSTER_UNITS] == F.roster_character_ids(t35, 0) and fresh[F.ROSTER_SIZE:F.ROSTER_SIZE + 4] == HEAP_HDR
ev["D_roster_full"] = {
    "static": {"alloc": "0x25d54 push 0xa00; call 0x3706e(malloc)→ [0x53bf7]:剛好 32 筆",
               "join": "0x112a5 不檢查容量;寫入 +5..+0x4f 的大部分欄位,不寫 +0..+4、+0x17、+0x19",
               "heap": "名冊前 4 bytes = 0x00000a05(大小 0xa04,最低位 1 = 使用中);緊接在名冊後 = 0x00000305 區塊,資料 0x1fd0c4 = [0x53a65] 基準調色盤快取(0x11df2 淡入淡出從這裡取 RGB)",
               "natural_max": "全 EXE 28 個 call 0x112a5、28 個不同角色(per_chapter_join_table.json)→ 正常流程最多 28 人;到 33 要 5 次以上重複的事件 0"},
    "join_overflow_v9b": {"filled": jn["filled"], "count_before": jn["count"], "count_forced": jn["count_forced"],
                          "count_after": af["roster"]["count"],
                          "changed_offsets_rel_roster+0xa00": ch, "heap_header_after": ta_[U:U + len(HEAP_HDR)].hex(),
                          "palette_bytes_changed": len([c for c in ch if c >= len(HEAP_HDR)]), "rec32_hex": ta_[U:][:U].hex()},
    "battle_save_33": {"count_byte": rt33["persistent_count"],
                       "roster_0xa00_equals_memory": s33[R:R + F.ROSTER_SIZE] == m33[:F.ROSTER_SIZE],
                       "record32_saved": s33[R + F.ROSTER_SIZE:R + F.ROSTER_SIZE + U] == m33[F.ROSTER_SIZE:F.ROSTER_SIZE + U]},
    "writeback_33": {"copies_unit_roster_hdr": cp, "header_overwritten_at": hdr_change,
                     "header_new_value_is_unit4_+0..+3": cp[k_hdr][2] == "102b0400",
                     "screen": "酒店畫面顏色錯亂(w1_after2.png):第 32..34 筆寫進調色盤快取,淡入時套用"},
    "tavern_save_35": {"memory_count": len(r35), "memory_ids_32_34": ids35[F.ROSTER_UNITS:],
                       "slot_count_byte": cnt35, "slot_chapter": ch35,
                       "slot_roster_equals_memory_first_0xa00": t35[o:o + F.ROSTER_SIZE] == m35[:F.ROSTER_SIZE]},
    "fresh_load_v9d": {"count": len(r_fresh), "ids_0_31": char_ids(r_fresh)[:F.ROSTER_UNITS],
                       "rec32_34_+7_+8": [[fresh[i * 0x50 + 7], fresh[i * 0x50 + 8]] for i in (32, 33, 34)],
                       FIRST_KEY: fresh[F.ROSTER_SIZE:F.ROSTER_SIZE + int(FIRST_KEY.removeprefix("rec32_first"))].hex(),
                       "header_after_roster": fresh[F.ROSTER_SIZE:F.ROSTER_SIZE + len(HEAP_HDR)].hex(),
                       "screen": "酒店隊員清單底部:圖示是雜訊,出現「約拿」(id 21)、「凱麗」(id 12)與一筆名稱亂碼(c3_bottom.png);讀檔與清單都沒有當掉"},
}
assert ev["D_roster_full"]["fresh_load_v9d"]["rec32_34_+7_+8"] == [[63, 60], [25, 21], [20, 12]]
# 讀檔後的隊員表傾印恰為整數筆,筆數等於酒店存檔的筆數 byte
assert len(fresh) % 0x50 == 0 and len(fresh) // 0x50 == t35[o + 0xA01], (len(fresh), t35[o + 0xA01])

# ---------------- E ----------------
ev["E_static_roster_count"] = {
    "writers_of_0x53bfb": {"0x1041e": "戰況載入:= 快照中繼資料 +9", "0x1144c": "0x112a5 join:inc",
                           "0x25efa": "新遊戲:= 0", "0x26070": "章節存檔還原", "0x2999a": "load_game_menu"},
    "no_decrement": "對 [0x53bfb] 的 44 處參照裡沒有 dec / sub,沒有任何流程會移除名冊成員或去重",
    "battle_setup": "0x10a5b..0x10b19:依部署格把名冊 [0x53bf7] 逐筆 memcpy 0x50 到戰場單位",
}
ev["F_repeat_event0_side_effect"] = {
    "observed_v9b": "同一場戰鬥觸發 3 次事件 0:ACT7 每次把 #12 下移 2 格 → (8,47)→49→51→53(地圖外,H = 53);ACT8 把 #13 下移 1 格 → (6,51)",
    "hang": "敵人攻擊 #12 時 ai_attack_execute 0x154de 呼叫 focus_unit(12) → camera_step_to(8,53),卡在 y 迴圈 0x12d42(EDI = 53、游標 (8,52))",
    "source": "驅動的終端輸出(未存檔):0x12d42 停 4 次,EDI 53,堆疊 [esp+0x14] = 0x35、[esp+0x18] = ret 0x154e3、[esp+0x1c] = 0xc;單位表 #12 = (8,53)",
    "third_replicate_C_hang": "v9b 第 2 回合敵方:focus_unit(53) → camera_step_to(178,49),0x12d3b ESI = 0xb2、游標 (24,20)(續六十九的第三次重現)",
}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("written", OUT, len(OUT.read_bytes()))
