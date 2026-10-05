# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""由 t_v16.py 產生 t_v21.py:0x89 的失控 blit 在第一列開始前就以 LOGL + HEAVYLOG 錄下每一條指令(續七十五)。"""
from pathlib import Path

SP = Path(__file__).parent
src = (SP / "t_v16.py").read_text(encoding="utf-8")


def rep(old: str, new: str) -> None:
    global src
    assert src.count(old) == 1, old[:60]
    src = src.replace(old, new)


rep('"""續七十四 v16(由 t_v11 產生,加 blit 斷點)',
    '"""續七十五 v21(由 mk_t_v21 從 t_v16 產生):0x4ec16 讀到寬 0 時先傾印事前狀態,BPDEL、HEAVYLOG、arm LOGL,'
    '不再 resume,等計數用完自停或 E_Exit。\n原 v16 說明:')

rep('''    if eip in (0x4EC16, 0x4EC48):
        rec["width_bp"], rec["height_dx"] = rec["ebp"] & 0xFFFF, rec["edx"] & 0xFFFF
        set_bps(BASE + EVENT + ROWS)
        st["rows"] = 0
''', '''    if eip in (0x4EC16, 0x4EC48):
        rec["width_bp"], rec["height_dx"] = rec["ebp"] & 0xFFFF, rec["edx"] & 0xFFFF
        arm_trace(rec, n)
''')

rep('''def h_oom(rec: dict, n: int) -> None:''', '''WD = f"/home/kg701004/fd2-run-harness-{inst}"
TRACE = ["wsl", "-d", "Ubuntu", "--", "env", "FD2_TRACE_TMUX_SOCKET=fd2harness", "FD2_TRACE_MODE=LOGL", "bash",
         "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_exec_trace.sh"]
COUNT = sys.argv[7] if len(sys.argv) > 7 else "1000000"
PRE = [("ivt", 0x0, 0x500), ("vgabios", 0xC0000, 0x8000), ("ext1m", 0x100000, 0x100000)]


def trace(args: list[str]) -> str:
    import subprocess
    r = subprocess.run(TRACE + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return (r.stdout + r.stderr).strip()


def arm_trace(rec: dict, n: int) -> None:
    """停在 0x4ec16(寬高已讀進 BP / DX):事前狀態 → BPDEL → HEAVYLOG → LOGL。arm 之後遊戲立刻繼續跑,不可再 resume。"""
    rec["pre_dumps"] = {}
    for nm, lin, size in PRE:
        b = L.dump(lin, size, f"{tag}_pre_{nm}")
        rec["pre_dumps"][nm] = [hex(lin), len(b)]
    rec["cr_pane"] = [x for x in L.pane().splitlines() if "EIP=" in x or "EAX=" in x][:2]
    L.cmd("BPDEL *")
    rec["heavylog_out"] = trace(["heavylog", f"harness-{inst}"])
    time.sleep(1.5)
    rec["heavylog_pane"] = [x.strip() for x in L.pane().splitlines() if "Heavy cpu logging" in x][-1:]
    rec["arm_out"] = trace(["arm", f"harness-{inst}", COUNT, WD])
    st["traced"] = True


def wait_trace(max_s: float = 3600) -> None:
    """等 LOGL 計數用完(除錯器自己停住)或模擬器 E_Exit。只讀 pane / 檔案狀態,不送任何鍵。"""
    t0 = time.time()
    while time.time() - t0 < max_s:
        time.sleep(10)
        pane = L.pane()
        stt = trace(["status", WD])
        print("wait", int(time.time() - t0), stt.replace("\\n", " | ")[:300], flush=True)
        if "cpu log LOGCPU.TXT created" in pane:
            st["trace_end"] = "count_done"
            break
        if "E_Exit" in pane or not pane.strip():
            st["trace_end"] = "emulator_gone"
            break
    else:
        st["trace_end"] = "timeout"
    st["trace_wait_s"] = round(time.time() - t0)
    st["trace_status"] = trace(["status", WD])
    (L.out / f"{tag}_trace_end_pane.txt").write_text(L.pane(), encoding="utf-8")
    if st["trace_end"] == "count_done":
        # 計數用完時除錯器是從 CPU 迴圈內進入的:試讀暫存器與事後記憶體(v16 時 Alt+Pause 停不住、D / MEMDUMPBIN 不被接受)
        st["after_regs"] = {k: hex(v) for k, v in L.regs().items()}
        st["post_dumps"] = {}
        for nm, lin, size in PRE:
            try:
                b = L.dump(lin, size, f"{tag}_post_{nm}")
                st["post_dumps"][nm] = [hex(lin), len(b)]
            except Exception as e:  # noqa: BLE001 —— 讀不到本身就是要記錄的結果
                st["post_dumps"][nm] = ["error", repr(e)[:200]]
        L.shot(f"{tag}_trace_end")


def h_oom(rec: dict, n: int) -> None:''')

rep('''        log.append(rec)
        print(json.dumps(rec, ensure_ascii=False)[:600], flush=True)
        n += 1
        save()
        L.resume()''', '''        log.append(rec)
        print(json.dumps(rec, ensure_ascii=False)[:600], flush=True)
        n += 1
        save()
        if st.get("traced"):
            wait_trace()
            save()
            print("done (traced)", json.dumps({k: st.get(k) for k in ("trace_end", "trace_wait_s")}), flush=True)
            return
        L.resume()''')

(SP / "t_v21.py").write_text(src, encoding="utf-8", newline="\n")
print("ok")
