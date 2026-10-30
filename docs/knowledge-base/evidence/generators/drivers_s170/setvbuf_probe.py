"""CALLLOG 的 `setvbuf(out, NULL, _IOFBF, 1 << 20)` 實際緩衝多大(續一百七十;續一百六十九仍留「4 KiB 是推得的」)。

在 WSL Ubuntu 用 ctypes 直接呼叫 DOSBox-X 連結的同一份 libc,照 CALLLOG 的寫法開檔、setvbuf、寫入長短不一的紀錄,
每寫一筆就看檔案大小(= 已寫盤的位置):
- A 受測:buf 傳 NULL、size 1 MiB(CALLLOG 的寫法)。
- B 對照:明確給一塊 1 MiB 的 buf —— 這才是真的 1 MiB 緩衝,寫 40000 位元組都不該寫盤;
  若 B 也提早寫盤,這個量法分不出兩者,A 的結果不算數。
- C 對照:不呼叫 setvbuf(glibc 預設)。
每段在中途做一次明確 fflush(位置故意不對齊),之後的寫盤位置應落在「fflush 位置 + k × 區塊」上
(續一百六十九 (A) 在 lc167a / lc168a 看到的就是這個樣子)。

測試檔放在 /home/kg701004 底下新建的暫存目錄(與 fd2-run-harness-* 同一個檔案系統,st_dev 會印出比對),
結束時只刪這個暫存目錄。不碰任何 harness 目錄。用法(WSL 內):python3 setvbuf_probe.py
"""
from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import shutil
import subprocess
import sys
import tempfile

HOME = "/home/kg701004"
DOSBOX = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
IOFBF = 0          # glibc <stdio.h> 的 _IOFBF
PHASE = 20000      # 每段寫入的位元組數
FLUSH_AT = 20000   # 第一段結束後明確 fflush;20000 不是 4096 的倍數

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
libc.fopen.restype = ctypes.c_void_p
libc.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
libc.setvbuf.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
libc.fwrite.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p]
libc.fflush.argtypes = [ctypes.c_void_p]
libc.fclose.argtypes = [ctypes.c_void_p]
libc.gnu_get_libc_version.restype = ctypes.c_char_p


def record_lengths(total: int) -> list[int]:
    """長短不一的紀錄長度(37 .. 341,接近 CALLLOG 的 C / E 行),合計恰為 total。"""
    out, i = [], 0
    while sum(out) < total:
        out.append(37 + (i * 97) % 305)
        i += 1
    out[-1] -= sum(out) - total
    return out


def run_case(path: str, mode: str) -> dict:
    """依 mode 開檔寫兩段,回傳每段觀察到的檔案大小集合。"""
    fp = libc.fopen(path.encode(), b"w")
    assert fp, "fopen 失敗"
    keep = None
    if mode == "null_1MiB":
        assert libc.setvbuf(fp, None, IOFBF, 1 << 20) == 0
    elif mode == "buf_1MiB":
        keep = ctypes.create_string_buffer(1 << 20)
        assert libc.setvbuf(fp, ctypes.cast(keep, ctypes.c_void_p), IOFBF, 1 << 20) == 0
    phases = []
    for ph in range(2):
        sizes = []
        for n in record_lengths(PHASE):
            assert libc.fwrite(b"x" * n, 1, n, fp) == n
            sizes.append(os.path.getsize(path))
        phases.append(sizes)
        if ph == 0:
            assert libc.fflush(fp) == 0
            assert os.path.getsize(path) == FLUSH_AT, "fflush 之後檔案大小應恰為已寫位元組"
    assert libc.fclose(fp) == 0
    del keep
    return {"phase0": sorted(set(phases[0])), "phase1": sorted(set(phases[1]))}


def main() -> int:
    ver = libc.gnu_get_libc_version().decode()
    ldd = subprocess.run(["ldd", DOSBOX], capture_output=True, text=True).stdout
    libc_line = next((ln.strip() for ln in ldd.splitlines() if "libc.so.6" in ln), "")
    mine = next((ln.split()[-1] for ln in open("/proc/self/maps") if "libc.so" in ln), "")
    dosbox_libc = libc_line.split("=>")[-1].split("(")[0].strip()      # 去掉載入位址(每次執行不同)
    same_libc = bool(dosbox_libc) and os.path.realpath(dosbox_libc) == os.path.realpath(mine)
    print(f"glibc {ver}; probe libc {os.path.realpath(mine)}; dosbox-x libc {os.path.realpath(dosbox_libc)}; same={same_libc}")

    d = tempfile.mkdtemp(prefix="s170-setvbuf-", dir=HOME)
    try:
        path = os.path.join(d, "probe.txt")
        open(path, "w").close()
        st = os.stat(path)
        blk = st.st_blksize
        # CALLLOG.TXT 寫在 fd2-run-harness-<name>/ 底下;只讀 stat,不碰內容
        hd = sorted(glob.glob(os.path.join(HOME, "fd2-run-harness-*")))
        same_fs = bool(hd) and all(os.stat(h).st_dev == st.st_dev for h in hd)
        print(f"testdir st_dev={st.st_dev} home st_dev={os.stat(HOME).st_dev} st_blksize={blk}; "
              f"harness dirs {len(hd)} same_fs={same_fs}")
        res = {m: run_case(path, m) for m in ("null_1MiB", "buf_1MiB", "default")}
    finally:
        shutil.rmtree(d)
    for m, r in res.items():
        print(f"{m}: phase0 sizes {r['phase0']}")
        print(f"{m}: phase1 sizes {r['phase1']}")

    def on_grid(sizes: list[int], base: int, step: int) -> bool:
        return all(s >= base and (s - base) % step == 0 for s in sizes)

    a, b, c = res["null_1MiB"], res["buf_1MiB"], res["default"]
    checks = {
        "DOSBox-X 與探針是同一份 libc": same_libc,
        "測試檔與 fd2-run-harness-* 同一個檔案系統": same_fs,
        "A 第一段:寫盤位置都是 st_blksize 的倍數、且有 ≥ 4 個": on_grid(a["phase0"], 0, blk) and len(a["phase0"]) >= 4,
        "A 第二段:寫盤位置都是 fflush 位置 + k × st_blksize、且有 ≥ 4 個":
            on_grid(a["phase1"], FLUSH_AT, blk) and len(a["phase1"]) >= 4,
        "A 與 C(預設)寫盤位置相同": a == c,
        "B 對照(真 1 MiB):兩段都沒寫盤": b["phase0"] == [0] and b["phase1"] == [FLUSH_AT],
    }
    for k, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + k)
    ok = all(checks.values())
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
