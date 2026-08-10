# FD2 重製專案進度（本地個人分支，未推送回 fd2_re 上游）

此檔記錄使用者個人重製目標（Win11 原生執行、1080P、角色美術升級、過場加速、
關卡隱藏條件顯示）在 `wicanr2/fd2_re` 這份 clone 上的實作進度。**這是本地個人
使用的衍生工作，不是要推送回上游 GitHub repo 的貢獻**，所以沒有完全套用
`AGENTS.md` 裡針對多人協作/上游 PR 的流程規則（例如 Docker-only IDA/Capstone、
commit 身分等），但沿用了其核心工程紀律：型別化資料、單元測試、誠實的證據等級
標示、不確定就不硬做（fail-closed）。

## 第 0 步：原生 Windows 11 建置與執行 —— ✅ 完成

- 安裝 Go 1.26.5（`winget install GoLang.Go --silent`）。
- Clone 至 `C:\Users\kg701\Desktop\GAME\fd2_re`。
- **原生 `go build`，不需要 Docker、不需要 CGO/gcc**——比 fd2_re 自己 README 記載
  的「只驗證過 Docker 交叉編譯，執行未在真機驗證」更簡單的路徑，這次直接證實可行。
- 用 `tools/unpack_dat.py --all` 解包使用者自己的原版遊戲檔案，資源數（FDFIELD
  100／FDOTHER 104／FDSHAP 67）跟本專案另一份格式逆向筆記（`FD2_format_notes.md`）
  的結果逐一吻合。
- 用 `tools/export_engine_assets.py` 產生 stage 0 資產，**實際執行成功**，視窗
  標題「炎龍騎士團2 重製 (fd2_re)」，畫面渲染出序章村莊小島地圖，且畫布本來就是
  hi-res 可縮放渲染，不是死板 320×200。

## Windows CJK 字型相依性修正 —— ✅ 完成（真實 bug fix）

`cmd/fd2/font.go` 原本的 `fontPaths` 只列 Linux 系統字型路徑
（`/usr/share/fonts/...`），在 Windows 上 `loadFont()` 會直接回傳 `nil`，
所有文字完全不渲染、且沒有任何錯誤訊息。已加入 Windows 內建繁體中文 UI 字型
「微軟正黑體」（`C:\Windows\Fonts\msjh.ttc`）與備援「細明體」路徑。用
`git stash` 前後對照確認：這個修正**不影響**既有 `cmd/fd2` 測試套件的通過/
失敗狀態（既有失敗全部是缺少 `assets/maps/mapN/tileset.png` 這類尚未產生的
逐章資產，跟這次的修改無關，已用 stash 前後對照驗證過是同樣的失敗）。

## 關卡隱藏條件顯示 —— ✅ 資料層＋獨立畫面完成，尚未接進主遊戲迴圈

**資料層**：新增 `remake/internal/objectives` package，把
`docs/knowledge-base/28-chapter-objectives-and-recruits.md` 整理的全 30 章
勝利/失敗/加入條件轉成型別化 Go 資料，標明證據等級 E3（玩家攻略整理，非原始
執行檔逐位元組驗證），並附完整單元測試（章節數完整性、必要欄位非空、抽樣
核對三個章節的實際內容）。

**畫面層**：新增獨立可執行檔 `remake/cmd/objectives-viewer`，用 Ebiten 渲染
一個乾淨的關卡目標畫面（章節標題、勝利條件、失敗條件含額外護衛目標、可能
加入角色與條件、置底的證據等級與操作提示）。**已實際建置並執行成功**，視覺
截圖確認排版、配色、中文字型渲染全部正常。章節切換邏輯（←/→鍵，1-30 夾邊）
抽出成純函式並用單元測試覆蓋（`nextChapter`/`prevChapter`），因為 OS 層級
的 `SendKeys` 按鍵無法可靠送達 Ebiten 這類走 raw input 的遊戲視窗，改用單元
測試驗證比硬套 UI 自動化更可靠。

**刻意不做的部分（誠實記錄）**：沒有把這個畫面接進 `cmd/fd2/main.go` 現有
7897 行、高度精細的原生行為重現狀態機（`Game.Update()`/`Draw()`）。那份狀態
機有大量 `native_*` 前綴的欄位跟邏輯，是逐一比對反組譯結果做出來的，貿然在
有限時間內插入未經完整理解的新畫面，風險遠高於「先交付一個獨立、乾淨、可驗證
正確的垂直切片」。**這是刻意的技術決策，不是没做完**：資料層跟畫面渲染都已經
是可以直接運作的東西，真正整合進主遊戲迴圈（在哪個時機點呼叫、如何跟現有
`campaign` package 的章節推進邏輯串接）需要先完整讀懂主迴圈的既有慣例，
是下一階段的工作。

## 過場加速 —— ✅ 完成

新增 `remake/cmd/fd2/cutscene_speed.go`：全域加速倍率 `cutsceneSpeedUp`（預設
5 倍，環境變數 `FD2_CUTSCENE_SPEED=1` 可還原原版節奏做 A/B 對照）。做法刻意
保守：只調整鏡頭平移（pan）、走位（walk）、淡出淡入（fade）、delay 拍、
native 過場揭幕（transition_reveal）、行軍蒙太奇自動轉場、戰鬥中過場事件
延遲、片頭 AFM/靜態幕等**計時器每 tick 前進多少**，不改 `beatStart` 等處
設定的原始 frames/delay 數值——那些數值仍是逐一對照反組譯位址的證據
（doc50/doc46 註解保持真實有效）。**刻意不動** `stepOriginalActing`
（doc50 §1.2 逐 tick 精確重現原版格線位移）：那段每個 tick 值本身就是行為
的一部分，跳 tick 會漏放中間格，風險評估後排除。

新增 5 個單元測試涵蓋環境變數解析與倒數計時 floor-at-0 邏輯，全部通過。跑
全套 `cmd/fd2` 既有測試時，發現這個改動讓 3 個逐 tick 精確節奏驗證測試失敗
（它們預設 1 tick=1 原生幀）；修法是加 `TestMain` 讓整個測試套件固定用原版
節奏跑，只有實際遊玩才吃加速倍率。用 `git stash` 前後對照確認：現在的失敗
數（13個）跟改動前 baseline 完全一致，都是既有缺資產（`assets/maps/mapN/
tileset.png`）問題，沒有引入新迴歸。

## 關卡目標畫面接進主迴圈 —— ✅ 完成

觸發點是 beat「loadch」(`cmd/fd2/main.go` case "loadch"):`applyLoadCH` 成功
套用章節 map/roster/script 後,若 `internal/objectives.ByNumber(chapter)` 有該
章資料,就設 `g.objChapter` 並直接 `return`(不呼叫 `beatAdvance()`),讓畫面
先擋住過場;沒有資料的章節(序章、31-33 尾聲/番外)完全不受影響,行為跟這次
改動前一樣直接往下跑。

**索引換算是真正的風險點**,原本我在 `beat "loadch"` 那行直接寫
`objectives.ByNumber(b.LoadCH.Chapter)`,是錯的——比對
`assets/cutscenes/bindings/ch01_pre.json`(它的 loadch 設 `"chapter": 1` 但
`"script": "assets/story/ch02.json"`)跟 `TestApplyLoadCHDirectReplayUsesBindingPartyOrder`
(`Chapter: 0` 對應 `ch01.json`)兩份既有證據,加上 `internal/objectives`
package doc 自己就寫明「walkthrough chapter N == remake chapter index N-1」,
確認 `LoadCHState.Chapter` 是 0-based stage 編號,要 `+1` 才是攻略慣用的
1-based 章節數。改對後新增 2 個整合測試
(`objectives_screen_test.go`)用真實編譯出的 `ch01_pre.json` binding 全流程
驗證:loadch 成功套用 → 畫面擋住 beat runner(`beatIdx` 停在原地)→
`dismissObjectivesScreen()`(從 `campInput()` 的 Enter/Space 分支抽出的純
邏輯,理由同 objectives-viewer 抽 `nextChapter`/`prevChapter`:ebiten raw
input 視窗不保證吃得到 OS 層模擬按鍵)清畫面 → `beatIdx` 正確前進。

阻塞機制完全比照既有的「dialog beat 擋住直到 Enter」慣例(`campInput()` 裡
`case "cutscene":` 那段),畫面渲染重用引擎既有 `g.font`,沒有像
`cmd/objectives-viewer` 那樣另外複製一份字型載入邏輯。

**意外收穫(範圍外但值得記錄的真 bug)**:為了讓上面的整合測試真的跑得動,
需要 `assets/maps/map1/tileset.png`,而既有 `remake/assets/maps/` 底下 34 個
章節目錄都只有 `map.json`/`mapN_units.json`,完全沒有 `tileset.png`(這是
Phase 0 就誠實記錄過的已知缺口)。追查 `tools/export_engine_assets.py` 為何
對 map1 產生「cannot write empty image」時,發現 `extracted/raw/FDSHAP/` 的
67 個資源其實是「真實 tileset(大檔)/固定 1200 bytes 的非 tileset 資源」
交錯排列——**stage N 對應的是 FDSHAP 資源 `2×N`,不是資源 `N`**(2×0=0,
2×1=2,2×2=4…共 33 個偶數索引 tileset + 33 個奇數索引的其他資源 + 1 = 67,
數字剛好對得上)。用修正後的索引重跑,33 張地圖的 tileset.png 全部產出成功
(逐張比對 map.json 的 w/h/cols 與已入庫版本一致才覆蓋,只換 tileset.png,
沒動任何 map.json/units.json)。`cmd/fd2` 測試套件因此從 13 個既有失敗降到
2 個(`TestBattleWalkActivatesMap26Event63OnlyAfterLeftStepCommit` 是 map26
event63 觸發時機的既有邏輯問題、`TestBattleCh27...` 是另一個測試檔案自己的
相對路徑問題,都跟這次改動無關,也跟 tileset 資產無關)。這些 `tileset.png`
依 `remake/.gitignore`(`assets/maps/*/*.png`)不會進版本控制,跟其他玩家
衍生素材規則一致。

## 1080P 縮放渲染管線 —— ✅ 完成

調查後發現這項比想像中小:視窗**本來就可拖曳縮放**
(`ebiten.SetWindowResizingMode(WindowResizingModeEnabled)` 早已存在於
`main()`),Ebiten 對非整數縮放也**預設套用平滑 box filter**(`run.go`
`SetScreenFilterEnabled` 文件寫明「default state is true」)——渲染管線本身
不用重做,真正缺的只是「一啟動就已經很大」的預設體驗跟全螢幕捷徑:

- **F11 切換全螢幕**(`cmd/fd2/main.go` `Update()`,跟既有 F2/F3 全域鍵同一
  段):`ebiten.SetFullscreen(!ebiten.IsFullscreen())`。
- **`defaultWindowSize()`**:啟動時用 `ebiten.ScreenSizeInFullscreen()` 抓
  螢幕實際尺寸,選一個 640×400 邏輯畫布的最大整數倍(抓不到螢幕尺寸則退回
  原本的 2 倍 1280×800,行為不變)。純數學部分抽成 `windowScaleFor(sw,sh int)
  int`,4 個單元測試涵蓋:1920×1080 標準螢幕(驗到剛好是 2 倍,3 倍的
  1920 寬會壓線超過留白邊界)、2560×1440 大螢幕(3 倍)、螢幕尺寸查詢失敗
  fallback、小螢幕不會縮到比原本預設更小。
- `ebiten.SetWindowSizeLimits(logicalW, logicalH, -1, -1)`:最小維持 1 倍
  (640×400),避免玩家把視窗拖到不能用的大小。

實機驗證:重新建置後啟動,視窗確實大幅放大(截圖確認地圖渲染清晰、box
filter 平滑縮放無鋸齒),關掉背景程序後確認乾淨結束。F11 全螢幕切換因為
是按鍵輸入,沿用本專案已知的限制(SendKeys 類 OS 層按鍵不保證送達 Ebiten
raw input 視窗)不做 UI 自動化驗證,靠程式碼審閱(`ebiten.SetFullscreen`
是官方公開 API,用法直接)。

## 角色美術升級 —— 🔶 索爾單人試驗完成，尚未推廣/接線

完整過程、最終配方、踩過的坑、已知取捨,都記在
`C:\Users\kg701\Desktop\GAME\FD2\character_art_pilot_sol\README.md`
(連同定案圖檔),不重複寫在這裡。摘要:

- Real-ESRGAN(純放大銳利化)證實不夠——它不能做風格轉換,只能讓原圖「同風格
  更銳利」。
- 純 img2img 會被原圖的壓縮構圖(索爾原圖額頭空間窄)卡死比例,調 strength
  只能在「比例對但角色特徵跑掉」跟「特徵保留但比例不對」之間二選一。
- 最終解法是 txt2img **從零文字重建**(不碰原圖像素),身份特徵詞(深藍髮、
  紅頭巾、側臉)放 prompt 最前段避開 CLIP 77 token 截斷,模型用
  `gsdf/Counterfeit-V2.5`。定案版本經多輪外觀調整(髮型、體格、服裝、髮色)
  收斂而成。
- **已知未解決,留給下一階段**:(1) 這是靜態立繪,不是原本 DATO.DAT 的 4
  嘴型動畫幀;(2) 已實測比對證實原版頭像跟 FDFIELD/FIGANI 小精靈是同一套
  像素美術語言,新畫風跟它們會有明顯落差,要不要跟進重畫小精靈待決定;
  (3) 還沒接進 `cmd/fd2` 引擎的實際對話畫面;(4) 還沒推廣到其他 31 個角色。

## 既有失敗測試修復 —— ✅ 完成(2 個真 bug)

使用者追問「失敗的問題可以解決嗎」後深入查證,找到並修復 2 個真正的 bug(非
「尚未實作的功能」):

1. **`assets/map0_units.json` 錯誤路徑**:`main.go` 的 `loadGame()`/
   `resetBattle()` 預設值、`assets/scenarios/campaign.json`,以及
   `internal/battle` 兩個測試檔,都還在用地圖目錄改版前的舊扁平路徑
   `assets/map0_units.json`,但檔案實際位置早已是
   `assets/maps/map0/map0_units.json`。修正後 `TestBattleCh27MaterializesVerifiedViewWithPersistentHUD`、
   `TestLoadSerial0`、`TestChapter1SetupMaterializesYuniCommandZero` 三個測試轉綠。
2. **`native_turn_event_controls.json` 被 Windows CRLF checkout 損毀**(真正的
   根因,比原先以為的「event62/63 功能尚未接通」更根本):這份從 FDFIELD.DAT
   逐位元組提取的 event62/63 資料表在 `internal/battle/model.go` 用寫死的
   SHA256(`127c894c...`)做完整性驗證,git blob 本身(LF)雜湊完全對得上,
   但這台機器的 `core.autocrlf=true` 把 checkout 出來的工作目錄檔案轉成
   CRLF,雜湊變成 `457442b3...`,驗證失敗→`HasNativeTurnEventControlState`
   恆為 false→event62/63 整條鏈路(`ApplyNativeFieldTurnActivationEvent`)
   永遠回傳「complete native turn controls are absent」。這正是
   `TestBattleWalkActivatesMap26Event63OnlyAfterLeftStepCommit`、
   `TestAllEditableMapsCarryNativeRendererInputs`、
   `TestMap26LoadsDormantTurnRowsAndActivatesEvent63` 三個測試失敗的共同根因。
   修法:用 `git show HEAD:<path>` 取出精確的已提交位元組覆寫工作目錄檔案,
   並新增根目錄 `.gitattributes` 把這個檔案標記 `-text`,讓它永遠不受
   autocrlf 影響、不會在下次 checkout/clone 時又壞掉。三個測試全部轉綠,
   `internal/battle` 整個套件現在 100% 通過。

修完後全 repo (`go test ./...`) 只剩 4 個既有失敗,全部是缺原版遊戲檔案
(`internal/campaign` 3 個 DOSBox oracle 測試,需要
`org_game/炎龍騎士團/FLAME2/FDOTHER.DAT`)或既有資料校驗差異
(`internal/fdtxt` 1 個),都不是程式碼問題,環境/資料缺口,未動。
`cmd/fd2` 套件本身(實際遊戲會跑的部分)100% 通過。

**後續補完**:使用者原版遊戲檔案其實就在
`C:\Users\kg701\Desktop\GAME\FD2\`(這次重製工作最初解包用的那份),只是不在
這份 `fd2_re` clone 底下的 `org_game/` 路徑。用 Windows directory junction
(`New-Item -ItemType Junction`,不需要系統管理員權限)把
`fd2_re\org_game\炎龍騎士團\FLAME2` 接到那個資料夾,不複製檔案、`org_game/`
本來就在 `.gitignore` 不會被版控碰到。接上後 `internal/campaign` 3 個
DOSBox oracle 測試全部轉綠。

**最後一個失敗也查清楚了**:`internal/fdtxt` 那個「差 1」不是解碼器 bug,是
測試預期值本身打錯字元。用偵錯用的臨時測試把第 44 句對白全部 130 個字
dump 出來,發現最後 3 個字都是連續的 `0x0249`(原始位元組
`49 02 49 02 49 02 ff ff`,像是「……」省略號收尾),但舊測試預期最後一個字
是 `0x0248`,單純打錯一個字元。用 `TestChapterLoader30UsesFDTXTArchiveResource31`
(org_game 接上後這個測試現在真的會跑,不再 skip)交叉驗證:抽出來的
`.bin` 位元組跟直接讀原版 `FDTXT.DAT` resource 31 完全一致,證實資料本身
沒問題。已修正測試預期值,並加一段檢查明確說明這是「重複收尾字元」,不是
「解碼器誤重複輸出同一項」。

`go test ./...` 全 repo 現在 100% 通過,0 個失敗。

**設定可攜化**:原本的 junction 是我手動下指令建的,換機器/重灌就要重來。
改成 `tools/link_org_game.ps1`(不需要系統管理員權限):驗證來源資料夾有
FD2.EXE/FDOTHER.DAT/FDFIELD.DAT/FDTXT.DAT 才動作(fail-closed),已經接對
就跳過、接錯就先移除再重接,冪等可重複執行。用法:

```powershell
.\tools\link_org_game.ps1                    # 用預設路徑 C:\Users\kg701\Desktop\GAME\FD2
.\tools\link_org_game.ps1 -Source "D:\其他位置"  # 換位置/換機器時指定
```

## 效能優化(不額外花費,程式碼直接審閱)—— ✅ 完成

使用者要求「都要做,從簡單的開始」,依風險由低到高逐項處理,每項都
`gofmt -w`+`go build ./...`+`go test ./cmd/fd2/...` 驗證只剩同一組 2 個
既有 baseline 失敗(`TestBattleWalkActivatesMap26Event63OnlyAfterLeftStepCommit`
map26 event63 時機問題、`TestBattleCh27...` 相對路徑問題,皆跟本次改動無關)。

1. **`objectives_screen.go` 面板背景/邊框快取**:`drawObjPanel` 原本每幀
   `ebiten.NewImage()` 重新配置 GPU 材質(這畫面擋住玩家輸入,可能連續畫
   上百幀),改成 lazy 建一次存 `g.objPanelBG`/`objPanelBorderH`/`objPanelBorderV`
   重複貼,比照既有 `g.dlgGrad` 慣例。
2. **移除 `globalPortraits` 全域變數重複**:Jules 那次 PR 引入的
   `dlgWrap`/`dlgPageCount` 改回 `*Game` 方法直接讀 `g.portraits`,不再維護
   一份跟 `Game` struct 平行的全域拷貝。
3. **對話框無素材 fallback 純色框快取**:`main.go` 與 `ending_preview.go`
   兩處原本各自每幀 `ebiten.NewImage(620,198)`,改成共用 `g.dlgBoxFallback`
   lazy 建一次。
4. (評估後判定非問題,未動)`drawNum` 逐幀 `fmt.Sprintf`:實際只是格式化
   字串,真正繪製用的是預載的 `g.digits[0-9]` 靜態材質,沒有材質配置成本,
   硬「優化」只會增加複雜度換不存在的效能提升。
5. **肖像圖延遲載入 + 平行解碼**(使用者明確要求「兩個都要」):`loadPortraits()`
   拆成 `loadPortraitIndex()`(開機只做便宜的檔名 glob+parse,不解碼)+
   `(g *Game) getPortraitFrames(speaker int)`(該角色第一次真的要顯示時才
   解碼,4 個嘴型幀用 goroutine 平行 `image.Decode`,`ebiten.NewImageFromImage`
   GPU 材質上傳留在呼叫端序列做,因為 Ebiten 不支援跨 goroutine 建材質)。
   放大後的肖像檔案變大,開機一次全解碼 137 人×4 幀的舊做法現在改成用多少
   角色、載多少,啟動更快。三個直接讀 `g.portraits[speaker]` 的地方
   (`dlgWrap`、`Draw()`、`ending_preview.go` 的 `drawNativeEndingDialogue`)
   都已改呼叫 `g.getPortraitFrames(speaker)`。
6. **`drawBattlePanel`/`drawUnit` 血條矩形改共用 1×1 白點材質**:這兩個函式
   原本用 `fillRect` 閉包每次都 `ebiten.NewImage(w,h)` 配置新材質畫實心矩形
   (`drawBattlePanel` 每次呼叫 4 個矩形、戰鬥攻擊演出每幀最多呼叫 2-3 次,
   是本次審閱中材質配置頻率最高的熱路徑),改成 lazy 建一次 `g.whitePixel`
   (1×1 白色),用 `GeoM.Scale(w,h)` 縮放+`ColorScale.Scale` 染色畫,不再
   每次配置 GPU 材質。同時發現並刪除了完全沒有呼叫端的死函式 `drawStatBar`
   (審閱時原以為是「待優化的血條」,實際 grep 全 repo 確認它從未被呼叫過,
   真正的血條繪製是 `drawBattlePanel` 裡的 `drawFill`/`fillRect`)。

## 角色美術升級 —— 🔶 索爾單人試驗完成，尚未推廣/接線

完整過程、最終配方、踩過的坑、已知取捨,都記在
`C:\Users\kg701\Desktop\GAME\FD2\character_art_pilot_sol\README.md`
(連同定案圖檔),不重複寫在這裡。摘要:

- Real-ESRGAN(純放大銳利化)證實不夠——它不能做風格轉換,只能讓原圖「同風格
  更銳利」。
- 純 img2img 會被原圖的壓縮構圖(索爾原圖額頭空間窄)卡死比例,調 strength
  只能在「比例對但角色特徵跑掉」跟「特徵保留但比例不對」之間二選一。
- 最終解法是 txt2img **從零文字重建**(不碰原圖像素),身份特徵詞(深藍髮、
  紅頭巾、側臉)放 prompt 最前段避開 CLIP 77 token 截斷,模型用
  `gsdf/Counterfeit-V2.5`。定案版本經多輪外觀調整(髮型、體格、服裝、髮色)
  收斂而成。
- **使用者最終決定放棄這個方向**(「算了 不改變圖片了」),改為更保守的
  務實目標:不重新設計圖片,只把**原始**角色頭像放大優化(Real-ESRGAN
  同畫風放大,`extracted/portraits_upscaled/`,80×80→320×320,137 角色×4
  嘴型共 544 張)並修正引擎原本寫死的頭像縮放假設(見下方效能優化第 5 項
  的 `getPortraitFrames`;縮放比例動態計算的修正由 Jules 完成,PR 已審閱
  合併)。

## 待辦（依序）

1. ~~過場加速~~ —— 已完成，見上。
2. ~~關卡目標畫面接進主迴圈~~ —— 已完成，見上。
3. ~~1080P 縮放渲染管線~~ —— 已完成，見上。
4. ~~原始角色頭像放大優化 + 動態縮放~~ —— 已完成，見上「角色美術升級」。
5. ~~效能優化(不額外花費)~~ —— 已完成，見上。
6. 角色美術「重新設計」(AI 生圖換畫風)—— 使用者已決定不做,見上。若未來
   要重啟,索爾試驗的完整記錄仍在
   `C:\Users\kg701\Desktop\GAME\FD2\character_art_pilot_sol\README.md`。

---
*最後更新：2026-08-10*
