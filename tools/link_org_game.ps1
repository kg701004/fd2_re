<#
.SYNOPSIS
  接上玩家自備的原版《炎龍騎士團2》遊戲檔案,讓需要 org_game/ 的測試與工具能跑。

.DESCRIPTION
  這份 repo 的 org_game/ 目錄不入版控(版權保護,見根目錄 .gitignore),但
  internal/campaign、internal/fdtxt 等套件的部分測試,以及 tools/ 底下的
  解包腳本,需要在 org_game/炎龍騎士團/FLAME2/ 底下找到玩家自己合法擁有的
  FD2.EXE / FDOTHER.DAT / FDFIELD.DAT 等原版檔案。

  這個腳本用 Windows directory junction(不需要系統管理員權限、不複製檔案)
  把 org_game/炎龍騎士團/FLAME2 接到你實際存放原版檔案的資料夾,換機器、
  重灌、資料夾搬家後重跑一次即可,不用再手動打 New-Item 指令。

.PARAMETER Source
  存放原版遊戲檔案(FD2.EXE、FDOTHER.DAT、FDFIELD.DAT...)的資料夾路徑。
  預設值是這次重製工作最初解包用的位置。

.EXAMPLE
  .\tools\link_org_game.ps1
  .\tools\link_org_game.ps1 -Source "D:\backup\FD2"
#>
param(
    [string]$Source = "C:\Users\kg701\Desktop\GAME\FD2"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Source)) {
    Write-Error "來源資料夾不存在:$Source`n請用 -Source 指定你實際存放原版遊戲檔案的資料夾。"
    exit 1
}

$required = @("FD2.EXE", "FDOTHER.DAT", "FDFIELD.DAT", "FDTXT.DAT")
$missing = $required | Where-Object { -not (Test-Path (Join-Path $Source $_)) }
if ($missing.Count -gt 0) {
    Write-Error "來源資料夾缺少必要檔案:$($missing -join ', ')`n$Source 看起來不是完整的原版遊戲檔案位置。"
    exit 1
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$parent = Join-Path $repoRoot "org_game\炎龍騎士團"
$link = Join-Path $parent "FLAME2"

New-Item -ItemType Directory -Force -Path $parent | Out-Null

if (Test-Path $link) {
    $existing = Get-Item $link
    if ($existing.LinkType -eq "Junction" -and $existing.Target -eq $Source) {
        Write-Output "已經接好了,無需重做:$link -> $Source"
        exit 0
    }
    Write-Output "移除舊連結:$link(原指向:$($existing.Target))"
    Remove-Item $link -Force
}

New-Item -ItemType Junction -Path $link -Target $Source | Out-Null
Write-Output "已接上:$link -> $Source"
Write-Output "驗證:go test ./... 應該全部通過(在 remake/ 目錄下執行)。"
