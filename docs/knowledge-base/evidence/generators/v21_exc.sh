#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十五 v21:逃逸(第 7060958 行)之前所有不在 blit 迴圈內的指令 —— 中斷出差的入口、EDI(寫到哪)
cd ~/fd2-run-harness-v21 || exit 1
awk 'NR<=7060957 && $2 !~ /^0170:001EAC(1F|24|25|66|68|6A|6C|6D|6E|70|72|74|75|77|7A|7B)$/ {
  e = index($0, "EDI:"); c = index($0, "CR0:");
  print NR, $2, substr($0, e, 12), substr($0, c, 12)
}' LOGCPU.TXT > /tmp/v21_exc.txt
wc -l < /tmp/v21_exc.txt
# 每段出差的第一行(前一行行號不連續)
awk 'NR==1 || $1 != prev+1 {print} {prev=$1}' /tmp/v21_exc.txt > /tmp/v21_exc_entries.txt
wc -l < /tmp/v21_exc_entries.txt
awk '{print $2}' /tmp/v21_exc_entries.txt | sort | uniq -c | sort -rn | head
echo "--- first 5 / last 8 entries"
head -5 /tmp/v21_exc_entries.txt
tail -8 /tmp/v21_exc_entries.txt
echo "--- last excursion in full"
last=$(tail -1 /tmp/v21_exc_entries.txt | awk '{print $1}')
awk -v s="$last" '$1 >= s' /tmp/v21_exc.txt | head -60
