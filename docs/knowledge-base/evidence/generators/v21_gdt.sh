#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十五 v21:stosb 寫到 GDT(base 0x170010)時寫了什麼 —— 0070 / 0080 / 0170 / 0178 四個描述子的 8 bytes;
# 以及逃逸後第一次進 C3FF 段之前的最後幾條指令。
cd ~/fd2-run-harness-v21 || exit 1
awk '$2 == "0170:001EAC24" {
  e = index($0, "EDI:"); a = index($0, "EAX:");
  edi = substr($0, e + 4, 8); al = substr($0, a + 10, 2);
  print edi, al
}' LOGCPU.TXT | awk '$1 >= "00170010" && $1 <= "00170657"' > /tmp/v21_gdt_writes.txt
wc -l < /tmp/v21_gdt_writes.txt
grep -E '^001700(8|9)' /tmp/v21_gdt_writes.txt | tr '\n' ' '; echo
grep -E '^0017018' /tmp/v21_gdt_writes.txt | tr '\n' ' '; echo
echo "--- first C3FF entry"
n=$(grep -n -m1 ' C3FF:' LOGCPU.TXT | cut -d: -f1)
echo "line $n"
sed -n "$((n-12)),$((n+2))p" LOGCPU.TXT | cut -c1-150
echo "--- first INT 6 handler entry"
m=$(grep -n -m1 ' F000:0000CA60' LOGCPU.TXT | cut -d: -f1)
echo "line $m"
sed -n "$((m-3)),$((m+1))p" LOGCPU.TXT | cut -c1-150
