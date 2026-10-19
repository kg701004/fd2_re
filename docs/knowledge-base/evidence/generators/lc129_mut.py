"""續一百二十九:lc129_analyze.py(靜態 / 軌跡,原 an129.py)與 lc129t_analyze.py(計時,原 an129t.py)的突變測試
(原暫存 mut129.py,續一百三十四移進倉庫;由 ev_cmd_table_0_9_coverage_lut_cycles.py 以子行程執行,輸出原樣寫進證據)。

改的是暫存複本(EXE 複本、live json 複本、紀錄 json 複本),原檔不動。每個突變要求:
回傳非 0、輸出有 FAIL / BAD 標記、而且指定的那一項真的被判失敗(或對照項被判成立),沒有 Traceback。
最後一行 "抓到 n / n,漏掉 0"。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _evpaths import GAME, ROOT as REPO  # noqa: E402
from _blobtools import LIVE_JSON  # noqa: E402
sys.path.insert(0, str(REPO / "tools"))
from disasm_le import lin2file  # noqa: E402
from le_xref import parse_le  # noqa: E402

EXE = GAME / "FD2.EXE"


def run(script: str, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def judge(name: str, rc: int, out: str, must: list[str]) -> bool:
    """must:每一行都要出現在輸出裡(例如 'FAIL stub_567')。"""
    ok = rc != 0 and ("FAIL" in out or "BAD" in out) and "Traceback (most recent" not in out and all(m in out for m in must)
    print("抓到" if ok else "漏掉", name, "| rc", rc, "| 缺", [m for m in must if m not in out])
    return ok


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mut129_"))
    data = EXE.read_bytes()
    meta = parse_le(data)
    caught = total = 0

    def exe_mut(name: str, patches: list[tuple[int, bytes, bytes]], must: list[str]) -> None:
        nonlocal caught, total
        b = bytearray(data)
        for lin, old, new in patches:
            off = lin2file(meta, lin)
            assert bytes(b[off:off + len(old)]) == old, (name, hex(lin), b[off:off + len(old)].hex())
            b[off:off + len(new)] = new
        p = tmp / f"{name}.EXE"
        p.write_bytes(bytes(b))
        total += 1
        caught += judge(name, *run("lc129_analyze.py", "--exe", str(p)), must)

    def live_mut(name: str, drop: list[str], add: list[str], must: list[str]) -> None:
        nonlocal caught, total
        d = json.loads(json.dumps(LIVE_JSON))
        s = [a for a in d["addresses"] if a not in drop] + add
        assert len(s) != len(d["addresses"]), name
        d["addresses"] = s
        p = tmp / f"{name}.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        total += 1
        caught += judge(name, *run("lc129_analyze.py", "--live", str(p)), must)

    # ---- an129.py:EXE 位元組
    exe_mut("stub5_push6", [(0x2145B, b"\x6a\x05", b"\x6a\x06")], ["FAIL stub_567"])
    exe_mut("stub2_jmp_off", [(0x21378, b"\xe9\x9d", b"\xe9\x9e")], ["FAIL stub_1238"])   # jmp rel32
    exe_mut("head0_push1", [(0x21218, b"\x6a\x00", b"\x6a\x01")], ["FAIL head_0"])
    exe_mut("head4_call_off", [(0x213AE, b"\xe8\x04\x00\x00\x00", b"\xe8\x05\x00\x00\x00")], ["FAIL head_4"])
    # 第 9 格改指到第 8 格的跳板(表在 obj2,raw 值 = 入口 - 0x10000)
    exe_mut("table9_to_stub8", [(0x51D01 + 9 * 4, (0x214AD - 0x10000).to_bytes(4, "little"),
                                 (0x21494 - 0x10000).to_bytes(4, "little"))], ["FAIL control_9_not_stub"])
    # ---- an129.py:軌跡
    live_mut("live_drop_h4", ["0x21396"], [], ["FAIL live_entries"])
    live_mut("live_add_h7", [], ["0x2147b"], ["FAIL live_entries", "FAIL not_ran"])
    live_mut("live_drop_body_b", ["0x213b7"], [], ["FAIL live_bodies"])

    # ---- an129t.py:紀錄 json 複本
    src = REPO / ".wsl_build"

    def runs_mut(name: str, sub: str, tag: str, fn, must: list[str]) -> None:
        nonlocal caught, total
        rd = tmp / name
        for s in ("lc129a_live", "lc129d_live"):
            (rd / s).mkdir(parents=True)
            for f in (src / s).glob("c*_s1*.json"):
                shutil.copy(f, rd / s / f.name)
        p = rd / sub / f"{tag}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        fn(d["stops"])
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        total += 1
        caught += judge(name, *run("lc129t_analyze.py", "--runs-dir", str(rd)), must)

    def shift_end(k: int):
        def f(st: list[dict]) -> None:
            for s in st:
                if s["at"] in ("0x21998", "0x219a8"):
                    s["tick"] += k
        return f

    def set_span(n: int):
        def f(st: list[dict]) -> None:
            t0 = st[0]["tick"]
            for s in st:
                if s["at"] in ("0x21998", "0x219a8"):
                    s["tick"] = t0 + n
                elif s["at"] == "0x2198e":
                    s["tick"] = min(s["tick"], t0 + n)
        return f

    runs_mut("t_nof_plus3", "lc129d_live", "c10000_s12_nof", shift_end(3),
             ["FAIL cycles 10000 法術 12:逐幀停與只停兩端相同", "FAIL 預測 cycles 10000 法術 12"])
    runs_mut("t_radius", "lc129a_live", "c2500_s12_frames", lambda st: st[5].__setitem__("radius", st[5]["radius"] + 1),
             ["FAIL c2500_s12_frames 站序"])
    runs_mut("t_args", "lc129d_live", "c10000_s11_nof", lambda st: st[0].__setitem__("args", [0, 15, 11]),
             ["FAIL c10000_s11_nof 站序"])
    runs_mut("t_ret", "lc129a_live", "c2500_s12_nof", lambda st: st[0].__setitem__("ret", "0x21888"),
             ["FAIL c2500_s12_nof 站序"])
    runs_mut("t_drop_end", "lc129a_live", "c2500_s12_nof", lambda st: st.__delitem__(1),
             ["FAIL 每份紀錄都有一個入口與一個迴圈結束"])
    runs_mut("t_s11_10000_is_7", "lc129d_live", "c10000_s11_nof", set_span(7),
             ["FAIL 預測 cycles 10000 法術 11", "FAIL 法術 11:2500 > 5000 > 10000"])

    # H0 世界:10000 的兩個法術都等於 5000(7 / 10)—— 對照 H0 必須轉為成立
    def h0_world() -> None:
        nonlocal caught, total
        rd = tmp / "t_h0_world"
        for s in ("lc129a_live", "lc129d_live"):
            (rd / s).mkdir(parents=True)
            for f in (src / s).glob("c*_s1*.json"):
                d = json.loads(f.read_text(encoding="utf-8"))
                if s == "lc129d_live":
                    set_span(7 if "s11" in f.name else 10)(d["stops"])
                (rd / s / f.name).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        total += 1
        caught += judge("t_h0_world", *run("lc129t_analyze.py", "--runs-dir", str(rd)),
                        ["對照 PASS 對照 H0", "FAIL 預測 cycles 10000 法術 12"])
    h0_world()
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"抓到 {caught} / {total},漏掉 {total - caught}")
    return 0 if caught == total else 1


if __name__ == "__main__":
    sys.exit(main())
