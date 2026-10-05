#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十七:每份 LOGL 追蹤裡,DOS/4GW 重置防護碼的關鍵點各出現幾次、在第幾行:
#   0C5C:00000B94(重置後進入點)、0C5C:0000032D(jmp 0018:0334 回保護模式)、0C5C:00001DFE(XMS 清理第一個 call far)
for v in "$@"; do
  f="$HOME/fd2-run-harness-$v/LOGCPU.TXT"
  printf '%s ' "$v"
  awk '/ 0C5C:00000B94 /{a = a " " NR} / 0C5C:0000032D /{b = b " " NR} / 0C5C:00001DFE /{c = c " " NR}
       END { printf "entry[%s ] jmp0018[%s ] xms[%s ]\n", a, b, c }' "$f"
done
