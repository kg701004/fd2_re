#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 唯讀檢查:有沒有殘留的 DOSBox-X、今天哪些 harness 檔被改過。
echo "== dosbox processes"
pgrep -a dosbox
echo "pgrep rc=$?"
echo "== harness dirs (newest first)"
ls -dt ~/fd2-run-harness-* | head -4
for d in $(ls -dt ~/fd2-run-harness-* | head -2); do
  echo "== files changed today in $d"
  find "$d" -type f -newermt "2026-10-13 00:00" -printf '%TY-%Tm-%Td %TH:%TM %s %p\n' | sort | tail -20
  echo "== FD2.EXE md5 in $d"
  find "$d" -maxdepth 3 -iname 'FD2.EXE' -exec md5sum {} \;
  echo "== save-like files in $d"
  find "$d" -maxdepth 3 -type f \( -iname '*.SAV' -o -iname 'FD2*.DAT' -o -iname '*.CFG' \) -printf '%TY-%Tm-%Td %TH:%TM %s %p\n' | sort | tail -12
done
