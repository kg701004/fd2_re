#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十五 v21:LOGCPU.TXT(5.4 GB,留在 WSL)的關鍵片段 → .wsl_build/ctr/v21/ch25/trace_excerpt.txt(每行前加原始行號)
cd ~/fd2-run-harness-v21 || exit 1
OUT=/mnt/c/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/v21/ch25/trace_excerpt.txt
c3=$(grep -n -m1 ' C3FF:' LOGCPU.TXT | cut -d: -f1)
i6=$(grep -n -m1 ' F000:0000CA60' LOGCPU.TXT | cut -d: -f1)
{
  echo "# lines $(wc -l < LOGCPU.TXT) bytes $(stat -c %s LOGCPU.TXT) sha256 $(sha256sum LOGCPU.TXT | cut -c1-64)"
  echo "# first_C3FF $c3 first_INT6_handler $i6"
  awk -v a=1 -v b=3 'NR>=a && NR<=b {print NR "\t" $0}' LOGCPU.TXT
  awk -v a=7039299 -v b=7039340 'NR>=a && NR<=b {print NR "\t" $0} NR>b {exit}' LOGCPU.TXT
  awk -v a=7060945 -v b=7060975 'NR>=a && NR<=b {print NR "\t" $0} NR>b {exit}' LOGCPU.TXT
  awk -v a=$((c3 - 14)) -v b=$((c3 + 3)) 'NR>=a && NR<=b {print NR "\t" $0} NR>b {exit}' LOGCPU.TXT
  awk -v a=$((i6 - 4)) -v b=$((i6 + 5)) 'NR>=a && NR<=b {print NR "\t" $0} NR>b {exit}' LOGCPU.TXT
  tail -n 3 LOGCPU.TXT | awk -v n=$(wc -l < LOGCPU.TXT) '{print n - 3 + NR "\t" $0}'
} > "$OUT"
wc -l "$OUT"
