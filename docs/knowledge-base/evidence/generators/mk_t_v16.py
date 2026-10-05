# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""由 t_v11.py 產生 t_v16.py:線性 7 = 0x89 載入假頭像之後,加斷點到頭像繪製 0x16559 與 RLE blit 0x4ebff / 0x4ec31 的每一步,
找出 DOSBox-X 結束前最後執行到的指令;模擬器結束時存下 tmux 面板並停止(v11 在結束後一直讀到全 0 暫存器)。"""
from pathlib import Path

SP = Path(__file__).parent
s = (SP / "t_v11.py").read_text(encoding="utf-8")


def rep(old: str, new: str) -> None:
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('"""續七十三 v11:', '"""續七十四 v16(由 t_v11 產生,加 blit 斷點):')
rep("OPEN_OFF = 1444",
    "BLIT = [0x16559, 0x1657C, 0x4EBFF, 0x4EC31, 0x4EC0C, 0x4EC0E, 0x4EC3E, 0x4EC40, 0x4EC16, 0x4EC48]\n"
    "ROWS = [0x4EC2A, 0x4EC5E]  # 每列結束(dec dx);讀到寬高後只看前 3 列,之後拿掉全部 blit 斷點讓它跑完\n"
    "OPEN_OFF = 1444")
# 0x161c5 寫入點讀完假頭像後掛上 blit 斷點
rep("    if st[\"l7_restore\"]:\n        L.sm(7, bytes([IVT7]))",
    "    if 0 <= st[\"k\"] <= LAST_K and CFG[st[\"k\"]][\"l7\"] == 0x89 and rec[\"eip\"] == \"0x161c5\":\n"
    "        set_bps(BASE + EVENT + BLIT)\n"
    "        st[\"blit\"] = True\n"
    "        rec[\"blit_armed\"] = True\n"
    "        rec[\"res_head32\"] = L.dump(rec[\"eax\"], 32, f\"{tag}_{n}_res32\").hex()\n"
    "    if st[\"l7_restore\"]:\n        L.sm(7, bytes([IVT7]))")
rep("def h_oom(rec: dict, n: int) -> None:",
    "def h_blit(rec: dict, n: int) -> None:\n"
    "    eip = int(rec[\"eip\"], 16)\n"
    "    rec[\"c67\"] = hex(G(0x53C67))\n"
    "    rec[\"a85\"] = hex(G(0x53A85))\n"
    "    if eip == 0x16559:\n"
    "        a = stack(L, rec, 2, f\"{tag}_{n}_args\")\n"
    "        rec[\"ret\"], rec[\"cell_idx\"] = hex(a[0] - DELTA), a[1]\n"
    "    if eip in (0x4EBFF, 0x4EC31):\n"
    "        a = stack(L, rec, 4, f\"{tag}_{n}_args\")\n"
    "        rec[\"ret\"], rec[\"dst\"], rec[\"src\"], rec[\"stride\"] = hex(a[0] - DELTA), hex(a[1]), hex(a[2]), a[3]\n"
    "    if eip in (0x4EC16, 0x4EC48):\n"
    "        rec[\"width_bp\"], rec[\"height_dx\"] = rec[\"ebp\"] & 0xFFFF, rec[\"edx\"] & 0xFFFF\n"
    "        set_bps(BASE + EVENT + ROWS)\n"
    "        st[\"rows\"] = 0\n"
    "    if eip in ROWS:\n"
    "        st[\"rows\"] = st.get(\"rows\", 0) + 1\n"
    "        rec[\"row\"], rec[\"dx_left\"] = st[\"rows\"], rec[\"edx\"] & 0xFFFF\n"
    "        if st[\"rows\"] >= 3:\n"
    "            set_bps(BASE + EVENT)\n"
    "            rec[\"rows_bp_removed\"] = True\n"
    "    st[\"blit_stops\"] = st.get(\"blit_stops\", 0) + 1\n"
    "\n\n"
    "def h_oom(rec: dict, n: int) -> None:")
rep("0x165AC: h_box, 0x111BA: h_load, 0x1636C: h_open, 0x16149: h_open, 0x1125E: h_oom}",
    "0x165AC: h_box, 0x111BA: h_load, 0x1636C: h_open, 0x16149: h_open, 0x1125E: h_oom,\n"
    "     **{a: h_blit for a in BLIT + ROWS}}")
# 模擬器結束偵測:停住時面板沒有 EIP= 或出現 E_Exit → 存面板、停止
rep("        idle = 0\n        rec = regs_rec(L)\n",
    "        idle = 0\n"
    "        pane = L.pane()\n"
    "        if \"E_Exit\" in pane or \"EIP=\" not in pane:\n"
    "            (L.out / f\"{tag}_crash_pane.txt\").write_text(pane, encoding=\"utf-8\")\n"
    "            st[\"emulator_gone\"] = True\n"
    "            print(\"EMULATOR GONE\", pane[-600:], flush=True)\n"
    "            break\n"
    "        rec = regs_rec(L)\n")
rep("        if eip in (0x15F84, 0x164AC, 0x16149, 0x1636C, 0x165AC, 0x1125E) or eip in WRITERS or \"trigger_k\" in rec:",
    "        if eip in (0x15F84, 0x164AC, 0x16149, 0x1636C, 0x165AC, 0x1125E) or eip in WRITERS or \"trigger_k\" in rec \\\n"
    "                or (eip in BLIT and st.get(\"blit_stops\", 0) <= 6):")
# 收尾:模擬器已結束就不要再 enter-debugger
rep("    from live import run as hrun\n    hrun([\"enter-debugger\", \"--instance\", inst])",
    "    if st.get(\"emulator_gone\"):\n"
    "        print(\"done (emulator gone)\", flush=True)\n"
    "        return\n"
    "    from live import run as hrun\n    hrun([\"enter-debugger\", \"--instance\", inst])")
(SP / "t_v16.py").write_text(s, encoding="utf-8")
print("ok", len(s))
