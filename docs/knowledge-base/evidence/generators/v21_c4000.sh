#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十五 v21:stosb 對 C3FF:0010(線性 0xC4000)附近與 C3FF:94C8(0xCD4B8)寫了什麼。
cd ~/fd2-run-harness-v21 || exit 1
awk '$2 == "0170:001EAC24" {
  e = index($0, "EDI:"); a = index($0, "EAX:");
  print substr($0, e + 4, 8), substr($0, a + 10, 2)
}' LOGCPU.TXT > /tmp/v21_all_writes.txt
wc -l < /tmp/v21_all_writes.txt
head -1 /tmp/v21_all_writes.txt; tail -1 /tmp/v21_all_writes.txt
grep -E '^000C400[0-F]' /tmp/v21_all_writes.txt | tr '\n' ' '; echo
grep -E '^000CD4(B[0-F]|C[0-F])' /tmp/v21_all_writes.txt | tr '\n' ' '; echo
# 單調遞增?(每次 stosb 的 EDI 比前一次大 1)
awk 'NR > 1 { d = strtonum("0x" $1) - p; if (d != 1) bad++ } { p = strtonum("0x" $1) } END { print "non-+1 steps:", bad + 0 }' /tmp/v21_all_writes.txt
