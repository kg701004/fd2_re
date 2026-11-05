#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十六:每份 LOGL 追蹤裡,重置後經 VGA BIOS(C000:00EE 的 INT 10h 轉送)印出的字元(AL),
# 以及逃逸後第一個 INT 21h AH=40h(寫檔)的行號。
for v in "$@"; do
  f="$HOME/fd2-run-harness-$v/LOGCPU.TXT"
  printf '%s ' "$v"
  awk '/ C000:000000EE /{ i = index($0, "EAX:"); printf "%c", strtonum("0x" substr($0, i + 10, 2)) }' "$f" | head -c 400 | tr '\r\n' '|~'
  echo
done
