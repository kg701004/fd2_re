"""make_passthrough_map.py —— 產生「完整預設綁定、只拿掉會攔截遊戲 F 鍵組合的 host 綁定」的 DOSBox-X mapper 檔。

起因(doc98 續一百九十一、續一百九十二):DOSBox-X 預設把 Ctrl+F2 綁成 hand_ejectpage、Ctrl+F5 綁成 hand_copyall,
xdotool 送進 Xvfb 的這兩個組合鍵只有 Ctrl 進得了 guest(K 紀錄只有 0x1d),第三章 / 第六章城鎮的秘密店 gate
(BIOS INT 16h 讀到 0x5F00 / 0x6200)因此永遠等不到鍵。舊的 tools/dosbox/passthrough.map 只列 5 個事件,
而 sdl_mapper.cpp `if (!MAPPER_LoadBinds()) CreateDefaultBinds();` —— 讀得到 mapper 檔就不建預設綁定,
所以那個檔讓所有鍵(連 Alt+Pause 進 debugger)都失效(lc191c)。

做法:不從原始碼猜綁定格式,讓 DOSBox-X 自己寫出預設綁定(`-startmapper` 開 mapper 編輯器、在私有 Xvfb 上點
Save 鈕,`MAPPER_SaveBinds` 寫出全部事件),再把 hand_* 事件裡「F1 .. F10 加 無 / Ctrl / Alt / Shift 單一修飾鍵、
沒有 host 旗標」的綁定拿掉(遊戲城鎮秘密店表用的就是 Shift / Ctrl / Alt + F1 .. F10 這一族 BIOS 掃描碼 0x54 .. 0x71)。
其他事件(key_* / mod_* / host / 其餘 hand_*,包括 hand_debugger 的 Alt+Pause)逐字保留。

用法:
  python tools/dosbox/make_passthrough_map.py generate [--bin DOSBOX_BIN] [--port N]
        # WSL 端跑 DOSBox-X 存出預設檔 → tools/dosbox/default_sdl2.map;去掉攔截綁定 → tools/dosbox/passthrough.map
  python tools/dosbox/make_passthrough_map.py check [RAW FINAL]
        # 離線檢查:FINAL 必須等於 strip(RAW),事件一個都不少,guest F 鍵族沒有任何 host 綁定,
        # key_f1 .. key_f10 / mod_1 .. mod_3 / hand_debugger 綁定都在
  python tools/dosbox/make_passthrough_map.py attest [--bin DOSBOX_BIN] [--port N]
        # 另一支 DOSBox-X:讓它寫出預設檔,與 default_sdl2.map 逐字相同才把它的 md5 加進 passthrough.map.binmd5
        # (harness 帶 FD2_HARNESS_MAPPER 時只接受 "<mapper>.binmd5" 列出的 binary;generate 也會更新這個檔)
  python tools/dosbox/make_passthrough_map.py --selftest

只在 WSL 端開 Xvfb + DOSBox-X(不載遊戲、不碰 harness 的 instance 與顯示埠範圍 199 .. 1999);產出檔是 DOSBox-X 的設定檔,
不是遊戲資產。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_PATH = HERE / "default_sdl2.map"
FINAL_PATH = HERE / "passthrough.map"
# 續一百九十三:passthrough.map 只對「預設綁定與 default_sdl2.map 逐字相同」的 DOSBox-X 成立。這個檔列出已核過的
# binary md5(一行一個);tools/dosbox_harness.sh 帶 FD2_HARNESS_MAPPER 時要求 "<mapper>.binmd5" 列有目前 binary 的 md5。
BINMD5_PATH = HERE / "passthrough.map.binmd5"
HEX = set("0123456789abcdef")
DEFAULT_BIN = "/home/kg701004/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x"
DEFAULT_PORT = 2399          # harness 用 199 + 100k(到 1999),這裡刻意在範圍外
SECTION = "[SDL2]"
# SDL2 scancode:F1 = 58 .. F10 = 67(SDL_SCANCODE_F1 起連號)
F_SCANCODES = {f"F{n}": 57 + n for n in range(1, 11)}
# DOSBox-X 預設 mod_1 = Ctrl(224 / 228)、mod_2 = Alt(226 / 230)、mod_3 = Shift(225 / 229);check() 會核對
MODS = {"": "", " mod1": "Ctrl+", " mod2": "Alt+", " mod3": "Shift+"}
EXPECT_MODS = {"mod_1": ["key 224", "key 228"], "mod_2": ["key 226", "key 230"], "mod_3": ["key 225", "key 229"]}
KEEP = {"hand_debugger": "key 72 mod2"}   # harness 進 debugger 的 Alt+Pause


def guest_binds() -> dict[str, str]:
    """遊戲需要 guest 收到的 F 鍵族:bind 字串 → 說明(例如 'key 59 mod1' → 'Ctrl+F2')。"""
    return {f"key {sc}{m}": f"{label}{fk}" for fk, sc in F_SCANCODES.items() for m, label in MODS.items()}


def parse_map(text: str) -> tuple[list[tuple[str, list[str]]], str]:
    """解析 MAPPER_SaveBinds 的輸出:回傳 ([SDL2] 段的 (事件, [綁定...]), 其後的原樣文字)。

    格式(sdl_mapper.cpp MAPPER_SaveBinds):第一行 `[SDL2]`,每個事件一行 `名稱 ` + 每個綁定 `"綁定" `,
    換行;其他段落原樣接在後面。綁定字串本身不含雙引號。
    """
    lines = text.split("\n")
    if not lines or lines[0] != SECTION:
        raise ValueError(f"第一行不是 {SECTION}")
    entries: list[tuple[str, list[str]]] = []
    i = 1
    while i < len(lines) and lines[i] and not lines[i].startswith("["):
        ln = lines[i]
        name, sep, rest = ln.partition(" ")
        if not name or not sep:
            raise ValueError(f"第 {i + 1} 行沒有事件名稱後的空白:{ln!r}")
        binds = []
        while rest:
            if not rest.startswith('"'):
                raise ValueError(f"第 {i + 1} 行綁定格式不符:{ln!r}")
            end = rest.index('"', 1)
            binds.append(rest[1:end])
            rest = rest[end + 1:]
            if not rest.startswith(" "):
                raise ValueError(f"第 {i + 1} 行綁定後沒有空白:{ln!r}")
            rest = rest[1:]
        entries.append((name, binds))
        i += 1
    return entries, "\n".join(lines[i:])


def render(entries: list[tuple[str, list[str]]], tail: str) -> str:
    """parse_map 的反函式(逐字同 MAPPER_SaveBinds 的格式)。"""
    body = "".join(f"{name} " + "".join(f'"{b}" ' for b in binds) + "\n" for name, binds in entries)
    return f"{SECTION}\n{body}{tail}"


def strip(entries: list[tuple[str, list[str]]]) -> tuple[list[tuple[str, list[str]]], list[tuple[str, str, str]]]:
    """拿掉 hand_* 事件裡屬於 guest F 鍵族的綁定;回傳 (新 entries, [(事件, 綁定, 說明)])。事件本身保留。"""
    g = guest_binds()
    out, removed = [], []
    for name, binds in entries:
        if name.startswith("hand_"):
            keep = []
            for b in binds:
                if b in g:
                    removed.append((name, b, g[b]))
                else:
                    keep.append(b)
            out.append((name, keep))
        else:
            out.append((name, list(binds)))
    return out, removed


def check(raw: str, final: str) -> list[str]:
    """回傳錯誤清單(空 = 通過)。"""
    errs: list[str] = []
    try:
        ents, tail = parse_map(raw)
    except ValueError as e:
        return [f"RAW 解析失敗:{e}"]
    if render(ents, tail) != raw:
        errs.append("RAW 經 parse → render 不能逐字還原(解析器不忠實)")
    d = dict(ents)
    if len(d) != len(ents):
        errs.append("RAW 有重複事件")
    for fk in ("F1", "F2", "F5", "F10"):
        if d.get(f"key_{fk.lower()}") != [f"key {F_SCANCODES[fk]}"]:
            errs.append(f"RAW 的 key_{fk.lower()} 不是 'key {F_SCANCODES[fk]}'(F 鍵 scancode 前提不成立)")
    for m, want in EXPECT_MODS.items():
        if d.get(m) != want:
            errs.append(f"RAW 的 {m} = {d.get(m)},不是 {want}(修飾鍵對應前提不成立)")
    want_ents, removed = strip(ents)
    if not removed:
        errs.append("RAW 沒有任何要拿掉的綁定(前提:預設至少有 Ctrl+F2 / Ctrl+F5)")
    if not {("hand_ejectpage", "key 59 mod1"), ("hand_copyall", "key 62 mod1")} <= {(n, b) for n, b, _ in removed}:
        errs.append("RAW 的 hand_ejectpage / hand_copyall 不是 Ctrl+F2 / Ctrl+F5")
    try:
        fents, ftail = parse_map(final)
    except ValueError as e:
        return errs + [f"FINAL 解析失敗:{e}"]
    if [n for n, _ in fents] != [n for n, _ in ents]:
        errs.append(f"FINAL 的事件 {len(fents)} 個與 RAW {len(ents)} 個不同(缺事件 = 該事件沒有任何綁定)")
    if final != render(want_ents, tail):
        errs.append("FINAL 不等於 strip(RAW)")
    g = guest_binds()
    left = [(n, b) for n, bs in fents if n.startswith("hand_") for b in bs if b in g]
    if left:
        errs.append(f"FINAL 仍有攔截 guest F 鍵的 host 綁定:{left}")
    fd = dict(fents)
    for name, b in KEEP.items():
        if b not in fd.get(name, []):
            errs.append(f"FINAL 的 {name} 沒有 {b!r}")
    if not all(fd.get(f"key_f{n}") for n in range(1, 11)):
        errs.append("FINAL 的 key_f1 .. key_f10 有空的")
    if ftail != tail:
        errs.append("FINAL 的其他段落與 RAW 不同")
    return errs


def parse_binmd5(text: str) -> list[str]:
    """解析 .binmd5:每行一個 32 位小寫 hex md5,LF 結尾、不可空、不可重複。

    Raises:
        ValueError: 格式不符。
    """
    if not text.endswith("\n") or "\r" in text:
        raise ValueError("要以 LF 結尾、不含 CR")
    md5s = text[:-1].split("\n")
    for m in md5s:
        if len(m) != 32 or not set(m) <= HEX:
            raise ValueError(f"不是 md5:{m!r}")
    if len(set(md5s)) != len(md5s):
        raise ValueError("md5 重複")
    return md5s


def render_binmd5(md5s: list[str]) -> str:
    """parse_binmd5 的反函式(排序、去重)。"""
    return "".join(f"{m}\n" for m in sorted(set(md5s)))


def attest_errors(raw_now: str, raw_committed: str, md5: str) -> list[str]:
    """這支 binary(md5)自己寫出的預設檔 raw_now 必須與已提交的 default_sdl2.map 逐字相同,passthrough.map 才適用。"""
    errs = []
    if len(md5) != 32 or not set(md5) <= HEX:
        errs.append(f"binary md5 格式不符:{md5!r}")
    if raw_now != raw_committed:
        a, b = dict(parse_map(raw_now)[0]), dict(parse_map(raw_committed)[0])
        diff = sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))
        errs.append(f"這支 DOSBox-X 的預設綁定與 default_sdl2.map 不同({len(diff)} 個事件,例如 {diff[:5]});"
                    "passthrough.map 不適用,要另外 generate")
    return errs


def next_binmd5(old_text: str | None, old_raw: str | None, new_raw: str, md5: str) -> str:
    """generate 之後的 .binmd5:預設檔沒變就併入原有清單,變了就只剩這支 binary。"""
    keep = parse_binmd5(old_text) if old_text is not None and old_raw == new_raw else []
    return render_binmd5(keep + [md5])


GEN_SCRIPT = r"""
set -u
BIN="$1"; PORT="$2"
pkill -f "Xvfb :$PORT " 2>/dev/null
tmp=$(mktemp -d "$HOME/fd2-mapgen-XXXXXX")
Xvfb ":$PORT" -screen 0 1024x768x24 -ac -nolisten tcp >"$tmp/xvfb.log" 2>&1 &
XP=$!
sleep 1.5
cd "$tmp"
DISPLAY=":$PORT" SDL_AUDIODRIVER=dummy "$BIN" -startmapper -set "sdl mapperfile=$tmp/default.map" >"$tmp/dosbox.log" 2>&1 &
DP=$!
w=""
for i in $(seq 1 40); do
  w=$(DISPLAY=":$PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
  [ -n "$w" ] && break
  sleep 0.25
done
sleep 3
echo "GEOM $(DISPLAY=":$PORT" xdotool getwindowgeometry "$w" | tr '\n' ' ')"
# Save 鈕:CreateLayout 的 CBindButton(PX(15), PY(20), BU(3), BV(1)) = (420, 390) 起 83 x 18,取中心(視窗座標)
DISPLAY=":$PORT" xdotool mousemove --window "$w" 461 399 click 1
for i in $(seq 1 20); do [ -s "$tmp/default.map" ] && break; sleep 0.25; done
sleep 0.5
kill $DP 2>/dev/null; sleep 0.5; kill $XP 2>/dev/null
echo "BINMD5 $(md5sum "$BIN" | cut -d' ' -f1)"
if [ -s "$tmp/default.map" ]; then echo "MAPB64 $(base64 -w0 "$tmp/default.map")"; else echo "NOMAP"; tail -5 "$tmp/dosbox.log"; fi
rm -rf "$tmp"
"""


def generate(bin_path: str, port: int) -> tuple[str, str]:
    """在 WSL 端讓 DOSBox-X 寫出預設 mapper 檔;回傳 (檔案文字, binary md5)。沒寫出檔就丟例外。"""
    import base64  # noqa: PLC0415
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", GEN_SCRIPT, "gen", bin_path, str(port)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    out = r.stdout.splitlines()
    geom = next((ln for ln in out if ln.startswith("GEOM ")), "")
    if "Geometry: 640x480" not in geom:
        raise RuntimeError(f"mapper 視窗不是 640x480,Save 鈕座標不適用:{geom!r} {r.stderr[-500:]}")
    md5 = next((ln.split()[1] for ln in out if ln.startswith("BINMD5 ")), "")
    b64 = next((ln.split()[1] for ln in out if ln.startswith("MAPB64 ")), None)
    if b64 is None:
        raise RuntimeError(f"DOSBox-X 沒寫出 mapper 檔:{out[-6:]} {r.stderr[-500:]}")
    return base64.b64decode(b64).decode("ascii"), md5


def selftest() -> int:
    """合成 fixture:拿掉的、留下的、與每個 check 規則各有成對對照。"""
    fails: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if not cond:
            fails.append(what)

    raw = ("[SDL2]\n"
           'hand_shutdown "key 66 mod1" \nhand_ejectpage "key 59 mod1" \nhand_copyall "key 62 mod1" \n'
           'hand_scrshot "key 19 host" \nhand_rawscrshot "key 59 mod1 host" \nhand_loadmap \n'
           'hand_debugger "key 72 mod2" \nhand_two "key 60 mod3" "key 4" \n'
           'mod_1 "key 224" "key 228" \nmod_2 "key 226" "key 230" \nmod_3 "key 225" "key 229" \nhost "key 69" \n'
           + "".join(f'key_f{n} "key {57 + n}" \n' for n in range(1, 11))
           + 'key_ctrl_f2 "key 59 mod1" \n'
           "\n[Other]\nfoo \n")
    ents, tail = parse_map(raw)
    expect(render(ents, tail) == raw, "round-trip")
    expect(dict(ents)["hand_two"] == ["key 60 mod3", "key 4"], "多綁定解析")
    expect(dict(ents)["hand_loadmap"] == [], "無綁定解析")
    expect(tail == "\n[Other]\nfoo \n", "尾段")
    new, removed = strip(ents)
    expect({(n, b) for n, b, _ in removed} == {("hand_shutdown", "key 66 mod1"), ("hand_ejectpage", "key 59 mod1"),
                                              ("hand_copyall", "key 62 mod1"), ("hand_two", "key 60 mod3")},
           f"拿掉的綁定 {removed}")
    nd = dict(new)
    expect(nd["hand_rawscrshot"] == ["key 59 mod1 host"], "host 旗標的綁定要留(要按 F12 才觸發)")
    expect(nd["hand_debugger"] == ["key 72 mod2"], "Alt+Pause 要留")
    expect(nd["hand_two"] == ["key 4"], "同事件的其他綁定要留")
    expect(nd["key_ctrl_f2"] == ["key 59 mod1"], "非 hand_ 事件不動")
    expect([n for n, _ in new] == [n for n, _ in ents], "事件一個都不能少")
    expect({n: d for n, _, d in removed}.get("hand_ejectpage") == "Ctrl+F2", "說明文字")
    good = render(new, tail)
    expect(check(raw, good) == [], f"正例 check:{check(raw, good)}")
    # 對照 1:lc191c 那種只列幾個事件的檔(缺事件 = 全鍵失效)
    partial = "[SDL2]\nhand_ejectpage \nhand_copyall \nhand_debugger \"key 72 mod2\" \n" + tail
    expect(any("事件" in e for e in check(raw, partial)), "部分 mapper 檔要 FAIL")
    # 對照 2:原樣(沒拿掉)
    expect(any("仍有攔截" in e for e in check(raw, raw)), "沒拿掉的檔要 FAIL")
    # 對照 3:多拿掉 Alt+Pause
    no_dbg = good.replace('hand_debugger "key 72 mod2" ', "hand_debugger ")
    expect(any("hand_debugger" in e for e in check(raw, no_dbg)), "拿掉 Alt+Pause 要 FAIL")
    # 對照 4:key_f2 沒綁(guest 收不到 F2)
    no_f2 = good.replace('key_f2 "key 59" ', "key_f2 ")
    expect(any("key_f1 .. key_f10" in e or "不等於" in e for e in check(raw, no_f2)), "key_f2 空要 FAIL")
    # 對照 5:RAW 的修飾鍵對應不同(前提)
    raw_swap = raw.replace('mod_1 "key 224" "key 228"', 'mod_1 "key 226" "key 230"')
    expect(any("mod_1" in e for e in check(raw_swap, render(strip(parse_map(raw_swap)[0])[0], tail))), "修飾鍵前提要 FAIL")
    # 對照 6:RAW 的 hand_ejectpage 不是 Ctrl+F2
    raw_np = raw.replace('hand_ejectpage "key 59 mod1"', 'hand_ejectpage "key 59 mod2"')
    expect(any("hand_ejectpage" in e for e in check(raw_np, render(strip(parse_map(raw_np)[0])[0], tail))),
           "ejectpage 前提要 FAIL")
    # 對照 7:解析器不忠實(行尾少空白)
    expect(any("解析" in e or "還原" in e for e in check(raw.replace('"key 69" \n', '"key 69"\n'), good)), "格式錯要 FAIL")
    # 對照 8:尾段被改
    expect(any("其他段落" in e for e in check(raw, good.replace("foo", "bar"))), "尾段不同要 FAIL")
    # 對照 9:空字串綁定(解析器的結尾引號從第 2 個字元起找)
    e_ents, _t = parse_map('[SDL2]\nhand_e "" "key 4" \n')
    expect(e_ents == [("hand_e", ["", "key 4"])], f"空綁定解析 {e_ents}")
    # 對照 10:只有 key_f1 空(RAW 與 FINAL 一致)也要被 key_f1 .. key_f10 那條抓到
    raw_f1 = raw.replace('key_f1 "key 58" ', "key_f1 ")
    expect(any("key_f1 .. key_f10" in e for e in check(raw_f1, render(strip(parse_map(raw_f1)[0])[0], tail))),
           "key_f1 空要 FAIL")
    # 對照 11:guest_binds 的族
    g = guest_binds()
    expect(len(g) == 40 and g["key 58 mod3"] == "Shift+F1" and g["key 67 mod2"] == "Alt+F10" and "key 68 mod1" not in g,
           "F 鍵族")
    # 對照 12 .. 16:.binmd5 與 attest(續一百九十三)
    m1, m2 = "0" * 31 + "1", "a" * 32
    expect(parse_binmd5(f"{m2}\n{m1}\n") == [m2, m1] and render_binmd5([m2, m1, m1]) == f"{m1}\n{m2}\n", "binmd5 往返")
    for bad in (f"{m1}", f"{m1}\r\n", f"{m1[:-1]}\n", f"{m2.upper()}\n", f"{m1}\n{m1}\n", "\n"):
        try:
            parse_binmd5(bad)
            fails.append(f"binmd5 壞格式要 ValueError:{bad!r}")
        except ValueError:
            pass
    expect(attest_errors(raw, raw, m1) == [], "attest 正例")
    expect(any("不同(1 個事件" in e and "hand_two" in e for e in attest_errors(raw.replace('"key 4" ', '"key 5" '), raw, m1)),
           "預設綁定不同要 FAIL 並指出事件")
    raw6 = raw
    for n in range(1, 7):
        raw6 = raw6.replace(f'key_f{n} "key {57 + n}" ', f'key_f{n} "key {157 + n}" ')
    e6 = attest_errors(raw6, raw, m1)
    expect(len(e6) == 1 and "不同(6 個事件" in e6[0] and "key_f5" in e6[0] and "key_f6" not in e6[0],
           f"6 個事件不同:只列前 5 個 {e6}")
    expect(any("md5 格式" in e for e in attest_errors(raw, raw, m1[:-1])), "md5 格式錯要 FAIL")
    expect(next_binmd5(f"{m2}\n", raw, raw, m1) == f"{m1}\n{m2}\n", "預設檔沒變:併入")
    expect(next_binmd5(f"{m2}\n", raw_f1, raw, m1) == f"{m1}\n", "預設檔變了:只剩新 binary")
    expect(next_binmd5(None, None, raw, m1) == f"{m1}\n", "第一次 generate")
    for f in fails:
        print("FAIL", f)
    print("selftest", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[0] == "--selftest":
        return selftest()
    if argv[0] == "generate":
        bin_path, port = DEFAULT_BIN, DEFAULT_PORT
        if "--bin" in argv:
            bin_path = argv[argv.index("--bin") + 1]
        if "--port" in argv:
            port = int(argv[argv.index("--port") + 1])
        raw, md5 = generate(bin_path, port)
        ents, tail = parse_map(raw)
        new, removed = strip(ents)
        final = render(new, tail)
        errs = check(raw, final)
        if errs:
            print("\n".join(errs))
            return 1
        old_raw = RAW_PATH.read_bytes().decode("ascii") if RAW_PATH.exists() else None
        old_md5s = BINMD5_PATH.read_bytes().decode("ascii") if BINMD5_PATH.exists() else None
        RAW_PATH.write_bytes(raw.encode("ascii"))
        FINAL_PATH.write_bytes(final.encode("ascii"))
        BINMD5_PATH.write_bytes(next_binmd5(old_md5s, old_raw, raw, md5).encode("ascii"))
        print(f"dosbox-x md5 {md5};事件 {len(ents)} 個;拿掉 {len(removed)} 個綁定:")
        for n, b, d in removed:
            print(f"  {n} \"{b}\" ({d})")
        for p in (RAW_PATH, FINAL_PATH):
            print(p.name, hashlib.md5(p.read_bytes()).hexdigest())
        return 0
    if argv[0] == "check":
        raw_p, fin_p = (Path(argv[1]), Path(argv[2])) if len(argv) >= 3 else (RAW_PATH, FINAL_PATH)
        errs = check(raw_p.read_bytes().decode("ascii"), fin_p.read_bytes().decode("ascii"))
        print("\n".join(errs) if errs else f"check PASS({fin_p.name} = strip({raw_p.name}))")
        return 1 if errs else 0
    if argv[0] == "attest":
        bin_path, port = DEFAULT_BIN, DEFAULT_PORT
        if "--bin" in argv:
            bin_path = argv[argv.index("--bin") + 1]
        if "--port" in argv:
            port = int(argv[argv.index("--port") + 1])
        committed = RAW_PATH.read_bytes().decode("ascii")
        errs = check(committed, FINAL_PATH.read_bytes().decode("ascii"))
        raw, md5 = generate(bin_path, port)
        errs += attest_errors(raw, committed, md5)
        if errs:
            print("\n".join(errs))
            return 1
        old = parse_binmd5(BINMD5_PATH.read_bytes().decode("ascii")) if BINMD5_PATH.exists() else []
        BINMD5_PATH.write_bytes(render_binmd5(old + [md5]).encode("ascii"))
        print(f"attest PASS:{bin_path}(md5 {md5})的預設綁定與 {RAW_PATH.name} 相同 → 已列入 {BINMD5_PATH.name}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
