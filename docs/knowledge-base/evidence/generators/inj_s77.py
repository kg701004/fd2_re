# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十七:受控注入 —— 原版 FD2.EXE 跑到標題選單後,在保護模式下把 DOS/4GW 的某個 GDT 描述子改成指定 byte × 8,
放開執行,讀 DOSBox-X 自己的記錄檔(FD2_HARNESS_LOGFILE=1)與 HEAVYLOG 看它怎麼失敗。

用法:python inj_s77.py <instance> <selector hex> <byte hex> <out_dir> [wait_s=90]
  例:inj_s77.py g3 0018 54 .wsl_build/ctr/inj/g3 —— 0018 的描述子(0x170028)改成 54 × 8(型別 0x14、DPL 2)
不改 FD2.EXE、不改存檔;只在記憶體裡改 8 bytes。注入前先確認 GDT / IDT 與續七十五~七十六的五次取樣相同。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
sys.path.insert(0, str(Path(__file__).parent))
import fd2_chapter_sweep as sw  # noqa: E402
from live import ROOT, Live, run  # noqa: E402
from reach_battle import is_title  # noqa: E402

GDT, IDT = 0x170010, 0x18A110
PRE = {0x18: "ffffc0c5009b0000", 0x70: "cf5730e0189b0000", 0x80: "3f5e2048179a0000"}
SP = "/mnt/c/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
TRACE = ["wsl", "-d", "Ubuntu", "--", "env", "FD2_TRACE_TMUX_SOCKET=fd2harness", "bash",
         "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_exec_trace.sh"]


def wsl_path(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    return "/mnt/" + s[0].lower() + s[2:]


def mode(pane: str) -> str | None:
    m = re.search(r"SS=[0-9A-Fa-f]{4} +(Real|Pr16|Pr32|VM86)", pane)
    return m.group(1) if m else None


def main() -> int:
    name, sel, byte, out = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16), ROOT / sys.argv[4]
    wait_s = float(sys.argv[5]) if len(sys.argv) > 5 else 90
    out.mkdir(parents=True, exist_ok=True)
    rec: dict = {"instance": name, "selector": f"{sel:04x}", "byte": f"0x{byte:02x}",
                 "descriptor_linear": hex(GDT + sel), "access": {"p": byte >> 7, "dpl": (byte >> 5) & 3,
                                                                  "type": f"0x{byte & 0x1F:02x}"}}
    if (out / "reach.json").exists():
        # 已由 reach_battle.py(同樣 FD2_HARNESS_LOGFILE=1)進到戰場:戰場裡遊戲跑在保護模式,IRQ 走 0070:42D1
        rec["state"] = "battle (reach_battle.py)"
    else:
        os.environ["FD2_HARNESS_LOGFILE"] = "1"
        os.environ["WSLENV"] = (os.environ.get("WSLENV", "") + ":FD2_HARNESS_LOGFILE").strip(":")
        sw.launch_instance(name, keepalive=3600)
        time.sleep(12)
        for i in range(60):
            sw.send_keys(name, "Escape")
            time.sleep(1.0)
            if i % 3 == 2 and is_title(sw.screenshot(name, out / "title.png")):
                break
        else:
            raise SystemExit("title menu never appeared")
        rec["state"] = f"title menu after {i + 1} Escape(s)"
    L = Live(name, out)
    # 標題選單時 CPU 幾乎都在實際模式(等鍵盤經 DOS / BIOS),盲停停不到保護模式:
    # 改在保護模式的計時器 IRQ 入口 0070:42D1 下斷點,停到後刪掉再注入(此時 CS 0070 已在快取裡)。
    run(["enter-debugger", "--instance", name])
    time.sleep(3)
    L.cmd("BP 0070:42D1")
    L.resume()
    regs = L.wait_stop(60)
    assert regs is not None and regs.get("EIP") == 0x42D1 and mode(L.pane()) in ("Pr16", "Pr32"), (regs, mode(L.pane()))
    L.cmd("BPDEL *")
    rec["halt"] = "BP 0070:42D1 (timer IRQ entry; 0070 is a 16-bit code segment, pane shows Pr16)"
    gdt = L.dump(GDT, 0x180, "pre_gdt")
    idt = L.dump(IDT, 0x100, "pre_idt")
    rec["pre"] = {f"{s:04x}": gdt[s: s + 8].hex() for s in PRE}
    assert rec["pre"] == {f"{s:04x}": v for s, v in PRE.items()}, rec["pre"]
    for v in (0x08, 0x0B, 0x0D):
        g = idt[v * 8: v * 8 + 8]
        assert g[2:4] == b"\x70\x00" and g[5] == 0x8E, (v, g.hex())
    r = subprocess.run(TRACE + ["heavylog", f"harness-{name}"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    rec["heavylog"] = (r.stdout + r.stderr).strip()[-200:]
    L.sm(GDT + sel, bytes([byte] * 8))
    after = L.dump(GDT + sel, 8, "post_inject")
    assert after == bytes([byte] * 8), after.hex()
    rec["injected"] = after.hex()
    rec["regs_at_inject"] = {k: hex(v) for k, v in L.regs().items()}
    L.resume()
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(5)
        p = L.pane()
        if "E_Exit" in p:
            break
    rec["waited_s"] = round(time.time() - t0)
    L.shot("end")
    subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", f"{SP}/inj_collect_s77.sh", name, wsl_path(out)],
                   capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"}, timeout=120)
    log = (out / "dosbox-x_log_excerpt.txt").read_text(encoding="utf-8", errors="replace")
    rec["log_key_lines"] = [x for x in log.splitlines() if re.search(
        r"CPU_Exception|Triple|CMOS Shutdown|E_Exit|Restart|reset", x)]
    (out / "inj.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rec, ensure_ascii=False)[:1500])
    sw.teardown(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
