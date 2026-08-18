package battle

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

// TestMoveCost_NoTerrainData_DefaultsFlat:State.Cost 為 nil(如舊測試直接手寫 State{}、
// 或 Load 找不到 map.json)時,MoveCost 全平地回 1,越界也回 1(不 panic)。
func TestMoveCost_NoTerrainData_DefaultsFlat(t *testing.T) {
	st := &State{W: 5, H: 5}
	if got := st.MoveCost(2, 2); got != 1 {
		t.Errorf("MoveCost = %d, want 1", got)
	}
	if got := st.MoveCost(-1, 0); got != 1 {
		t.Errorf("MoveCost(越界) = %d, want 1", got)
	}
	if got := st.MoveCost(99, 99); got != 1 {
		t.Errorf("MoveCost(越界) = %d, want 1", got)
	}
}

// TestMoveCost_FromTable:有 Cost 表時逐格查值(水=不可通行的 99、沼澤=2、平地=1)。
func TestMoveCost_FromTable(t *testing.T) {
	st := &State{W: 3, H: 1, Cost: []int{1, 99, 2}}
	cases := map[[2]int]int{{0, 0}: 1, {1, 0}: 99, {2, 0}: 2}
	for xy, want := range cases {
		if got := st.MoveCost(xy[0], xy[1]); got != want {
			t.Errorf("MoveCost(%d,%d) = %d, want %d", xy[0], xy[1], got, want)
		}
	}
}

// TestReachable_BlockedByTerrain:一整排不可通行地形(cost=99)擋在中間,單位過不去,
// 驗證「不可通行」不需要額外特判,靠 cost 夠大自然被 MV 篩掉(見 MoveCost 註解)。
func TestReachable_BlockedByTerrain(t *testing.T) {
	// 5x3 地圖,x=2 整欄是牆(cost=99),把地圖左右隔開。
	w, h := 5, 3
	cost := make([]int, w*h)
	for i := range cost {
		cost[i] = 1
	}
	for y := 0; y < h; y++ {
		cost[y*w+2] = 99
	}
	st := &State{W: w, H: h, Cost: cost}
	u := &Unit{Camp: Own, X: 0, Y: 1, MV: 10, HP: 1, MaxHP: 1, OnField: true}
	st.Units = []*Unit{u}
	reach := st.Reachable(u)
	for x := 3; x < w; x++ {
		for y := 0; y < h; y++ {
			if reach[Cell{x, y}] {
				t.Errorf("牆右側 (%d,%d) 不該可達(MV=10 仍應被 cost=99 擋停)", x, y)
			}
		}
	}
	if !reach[Cell{1, 1}] {
		t.Errorf("牆左側 (1,1) 應可達")
	}
}

// TestReachable_HighCostTerrainLimitsRange:沼澤(cost=2)比平地(cost=1)更耗 MV,
// 同樣 MV=3 的單位,走沼澤只能走 1 格,走平地能走 3 格——驗證 Reachable 真的按地形
// 差異扣血(進入格的成本查 s.Cost,不是每步固定 1),不是所有地形都當一步處理。
func TestReachable_HighCostTerrainLimitsRange(t *testing.T) {
	w, h := 5, 1
	swamp := make([]int, w*h)
	for x := 0; x < w; x++ {
		swamp[x] = 2 // 進入任何一格都是沼澤成本
	}
	flat := make([]int, w*h)
	for x := 0; x < w; x++ {
		flat[x] = 1
	}

	stSwamp := &State{W: w, H: h, Cost: swamp}
	uSwamp := &Unit{Camp: Own, X: 0, Y: 0, MV: 3, HP: 1, MaxHP: 1, OnField: true}
	stSwamp.Units = []*Unit{uSwamp}
	reachSwamp := stSwamp.Reachable(uSwamp)
	if !reachSwamp[Cell{1, 0}] {
		t.Errorf("沼澤:(1,0) 成本 2<=MV(3),應可達")
	}
	if reachSwamp[Cell{2, 0}] {
		t.Errorf("沼澤:(2,0) 累積成本 2+2=4>MV(3),不該可達")
	}

	stFlat := &State{W: w, H: h, Cost: flat}
	uFlat := &Unit{Camp: Own, X: 0, Y: 0, MV: 3, HP: 1, MaxHP: 1, OnField: true}
	stFlat.Units = []*Unit{uFlat}
	reachFlat := stFlat.Reachable(uFlat)
	if !reachFlat[Cell{3, 0}] {
		t.Errorf("平地:(3,0) 累積成本 1+1+1=3<=MV(3),應可達")
	}
}

// TestMoveCostFor_WalkUnchanged:MoveWalk(零值,現行所有角色的唯一值)必須跟原本的
// MoveCost 結果完全一樣,即使 NativeTerrainMoveCodes 有資料——確保這個欄位是純增量,
// 不改變任何既有角色的行為。
func TestMoveCostFor_WalkUnchanged(t *testing.T) {
	st := &State{W: 3, H: 1, Cost: []int{1, 99, 2}, NativeTerrainMoveCodes: []byte{2, 4, 3}}
	u := &Unit{MoveType: MoveWalk}
	for x, want := range map[int]int{0: 1, 1: 99, 2: 2} {
		if got := st.MoveCostFor(u, x, 0); got != want {
			t.Errorf("MoveCostFor(walk, %d,0) = %d, want %d(=MoveCost 原值)", x, got, want)
		}
	}
}

// TestMoveCostFor_CavalryForestAndSwamp:騎兵過森林(control byte 2/3)= 2,過沼澤
// (control byte 4)= 3,平地/中性(0/1/5)維持步行原值 1(doc02 §3.1)。
func TestMoveCostFor_CavalryForestAndSwamp(t *testing.T) {
	// x=0 平地(control 0),x=1 森林(control 2),x=2 沼澤(control 4)。
	// Cost 陣列全部烘焙成步行基準值(平地1、森林1、沼澤2),match 目前 map.json 匯出的實際狀態。
	st := &State{
		W: 3, H: 1,
		Cost:                   []int{1, 1, 2},
		NativeTerrainMoveCodes: []byte{0, 2, 4},
	}
	u := &Unit{MoveType: MoveCavalry}
	cases := map[int]int{0: 1, 1: 2, 2: 3}
	for x, want := range cases {
		if got := st.MoveCostFor(u, x, 0); got != want {
			t.Errorf("MoveCostFor(cavalry, %d,0) = %d, want %d", x, got, want)
		}
	}
}

// TestMoveCostFor_FlyIgnoresTerrain:飛行單位永遠 1,連沼澤也不例外——但不可通行地形
// (cost>=99,如牆/深水)仍然擋住,doc02 §3.1 沒有把「不可通行」跟地形成本表混在一起。
func TestMoveCostFor_FlyIgnoresTerrain(t *testing.T) {
	st := &State{
		W: 3, H: 1,
		Cost:                   []int{1, 2, 99},
		NativeTerrainMoveCodes: []byte{0, 4, 4},
	}
	u := &Unit{MoveType: MoveFly}
	if got := st.MoveCostFor(u, 0, 0); got != 1 {
		t.Errorf("MoveCostFor(fly, 平地) = %d, want 1", got)
	}
	if got := st.MoveCostFor(u, 1, 0); got != 1 {
		t.Errorf("MoveCostFor(fly, 沼澤) = %d, want 1(飛行忽略地形)", got)
	}
	if got := st.MoveCostFor(u, 2, 0); got != 99 {
		t.Errorf("MoveCostFor(fly, 不可通行) = %d, want 99(飛行仍擋不可通行地形)", got)
	}
}

// TestMoveCostFor_MissingTerrainCodesFallsBackToBase:NativeTerrainMoveCodes 長度
// 對不上(或沒有)時,騎兵/飛行都退回 MoveCost 原值,不 panic、不假造地形類型。
func TestMoveCostFor_MissingTerrainCodesFallsBackToBase(t *testing.T) {
	st := &State{W: 3, H: 1, Cost: []int{1, 2, 99}} // 沒有 NativeTerrainMoveCodes
	uCav := &Unit{MoveType: MoveCavalry}
	for x, want := range map[int]int{0: 1, 1: 2, 2: 99} {
		if got := st.MoveCostFor(uCav, x, 0); got != want {
			t.Errorf("MoveCostFor(cavalry, 無地形資料, %d,0) = %d, want %d(退回 MoveCost)", x, got, want)
		}
	}
}

// TestReachable_CavalryForestCostsMoreThanWalk:整合測試,直接用 Reachable 驗證——
// 同一張全森林地圖,MV=3 的騎兵只能走 1 格(成本2/格),同 MV 的步行單位能走 3 格
// (成本1/格),確認 MoveType 真的有接進 Reachable 的 BFS,不是只是孤立函式。
func TestReachable_CavalryForestCostsMoreThanWalk(t *testing.T) {
	w, h := 5, 1
	cost := make([]int, w)
	codes := make([]byte, w)
	for x := range cost {
		cost[x] = 1 // map.json 烘焙的步行基準值:森林對步行=1,跟平地相同
		codes[x] = 2 // FDSHAP control byte 2 = 森林
	}
	st := &State{W: w, H: h, Cost: cost, NativeTerrainMoveCodes: codes}

	walk := &Unit{Camp: Own, X: 0, Y: 0, MV: 3, MoveType: MoveWalk, HP: 1, MaxHP: 1, OnField: true}
	st.Units = []*Unit{walk}
	reachWalk := st.Reachable(walk)
	if !reachWalk[Cell{3, 0}] {
		t.Errorf("步行單位森林地圖 MV=3 應能走到 (3,0)(成本1/格)")
	}

	cav := &Unit{Camp: Own, X: 0, Y: 0, MV: 3, MoveType: MoveCavalry, HP: 1, MaxHP: 1, OnField: true}
	st.Units = []*Unit{cav}
	reachCav := st.Reachable(cav)
	if !reachCav[Cell{1, 0}] {
		t.Errorf("騎兵森林地圖 MV=3 應能走到 (1,0)(成本2)")
	}
	if reachCav[Cell{2, 0}] {
		t.Errorf("騎兵森林地圖 MV=3 不該走到 (2,0)(累積成本2+2=4>MV3);步行同樣 MV 可以但騎兵不行,這正是這個欄位存在的理由")
	}
}

// TestMoveCostFor_NativePerClassTableTakesPriority:0x4e555 的真實 29×20 表
// (docs/knowledge-base/11-enemy-ai.md「actor record+0x20 選 0x4E555 成本列」)
// 一旦載入,必須比舊的 doc02 三分類近似值優先。selector0(class 0)全表都是1、
// selector1(class 1)在 terrain index2 是 20(=擋)、index4 是 2——這兩個 class
// 拿同一格地形要算出不同結果,證明真的是照 class 分開查表,不是巧合。
func TestMoveCostFor_NativePerClassTableTakesPriority(t *testing.T) {
	rows, err := LoadNativeMovementCostRows("../../assets/data/native_movement_cost_rows.json")
	if err != nil {
		t.Fatalf("LoadNativeMovementCostRows: %v", err)
	}
	if got := rows[0][2]; got != 1 {
		t.Fatalf("fixture 假設 selector0 terrain2=1,實際=%d(資料表變了要重寫這個測試)", got)
	}
	if got := rows[1][2]; got != 20 {
		t.Fatalf("fixture 假設 selector1 terrain2=20,實際=%d(資料表變了要重寫這個測試)", got)
	}
	if got := rows[1][4]; got != 2 {
		t.Fatalf("fixture 假設 selector1 terrain4=2,實際=%d(資料表變了要重寫這個測試)", got)
	}
	st := &State{
		W: 2, H: 1,
		Cost:                   []int{1, 1},
		NativeTerrainMoveCodes: []byte{2, 4}, // x=0 對到 row index2、x=1 對到 row index4
		NativeMovementCostRows: rows,
	}
	class0 := &Unit{ClassID: 0, MoveType: MoveCavalry} // MoveType 蓋不掉原生表,證明優先序
	if got := st.MoveCostFor(class0, 0, 0); got != 1 {
		t.Errorf("MoveCostFor(class0, terrain2) = %d, want 1(selector0 全表皆1)", got)
	}
	class1 := &Unit{ClassID: 1}
	if got := st.MoveCostFor(class1, 0, 0); got != 99 {
		t.Errorf("MoveCostFor(class1, terrain2) = %d, want 99(row值20=這個class走不進去)", got)
	}
	if got := st.MoveCostFor(class1, 1, 0); got != 2 {
		t.Errorf("MoveCostFor(class1, terrain4) = %d, want 2(row值2)", got)
	}
}

// TestMoveCostFor_NativeRecordByte8OverridesSelectorToRow1:doc11「actor
// record+8==0x1C 時改用列1」——即使 ClassID 是別的值,只要 NativeRecordByte8==
// 0x1c,查表必須用 selector1,不是 ClassID。
func TestMoveCostFor_NativeRecordByte8OverridesSelectorToRow1(t *testing.T) {
	rows, err := LoadNativeMovementCostRows("../../assets/data/native_movement_cost_rows.json")
	if err != nil {
		t.Fatalf("LoadNativeMovementCostRows: %v", err)
	}
	st := &State{
		W: 1, H: 1,
		Cost:                   []int{1},
		NativeTerrainMoveCodes: []byte{2}, // row index2:selector0=1,selector1=20(擋)
		NativeMovementCostRows: rows,
	}
	u := &Unit{ClassID: 5, NativeRecordByte8: 0x1c, HasNativeRecordByte8: true}
	if got := st.MoveCostFor(u, 0, 0); got != 99 {
		t.Errorf("MoveCostFor(record+8==0x1c, terrain2) = %d, want 99(selector 應被強制改成1,不是ClassID5)", got)
	}
}

// TestMoveCostFor_Predicate1F183OverridesSelectorToRow19: doc11「0x1F183
// 成立時改用列19」——0x1f183 disassembly-confirmed 2026-08-14 as
// (record+0x20==0x13) OR (record+0x1f race in {4,5}); class 0x13 already
// hits row19 by default(no-op case), so the meaningful case is race-only.
func TestMoveCostFor_Predicate1F183OverridesSelectorToRow19(t *testing.T) {
	rows, err := LoadNativeMovementCostRows("../../assets/data/native_movement_cost_rows.json")
	if err != nil {
		t.Fatalf("LoadNativeMovementCostRows: %v", err)
	}
	st := &State{
		W: 1, H: 1,
		Cost:                   []int{1},
		NativeTerrainMoveCodes: []byte{2}, // terrain index2
		NativeMovementCostRows: rows,
	}
	class5Row2 := rows[5][2]
	row19At2 := rows[0x13][2]
	if row19At2 == class5Row2 {
		t.Fatalf("fixture 假設 class5 跟 row19 在 terrain2 的值不同,實際都是 %d(資料表變了要重寫這個測試)", row19At2)
	}
	u := &Unit{ClassID: 5, NativeRecordRace: 4, HasNativeRecordRace: true}
	want := 99
	if row19At2 < 20 {
		want = int(row19At2)
	}
	if got := st.MoveCostFor(u, 0, 0); got != want {
		t.Errorf("MoveCostFor(race=4 predicate, terrain2) = %d, want %d(selector 應被 0x1f183 改成 row19,不是 ClassID5)", got, want)
	}
}

// TestMoveCostFor_RecordByte8Row1OutranksPredicate1F183Row19: 0x14b78 反組譯
// 證實 record+8==0x1c 的檢查在 0x1f183 之後執行,同時成立時 row1 勝出。
func TestMoveCostFor_RecordByte8Row1OutranksPredicate1F183Row19(t *testing.T) {
	rows, err := LoadNativeMovementCostRows("../../assets/data/native_movement_cost_rows.json")
	if err != nil {
		t.Fatalf("LoadNativeMovementCostRows: %v", err)
	}
	st := &State{
		W: 1, H: 1,
		Cost:                   []int{1},
		NativeTerrainMoveCodes: []byte{2},
		NativeMovementCostRows: rows,
	}
	u := &Unit{
		ClassID: 5, NativeRecordRace: 5, HasNativeRecordRace: true, // triggers 0x1f183 -> row19
		NativeRecordByte8: 0x1c, HasNativeRecordByte8: true, // then row1 must win
	}
	want := 99
	if rows[1][2] < 20 {
		want = int(rows[1][2])
	}
	if got := st.MoveCostFor(u, 0, 0); got != want {
		t.Errorf("MoveCostFor(race=5且record+8==0x1c) = %d, want %d(row1 必須贏過 row19)", got, want)
	}
}

// TestMoveCostFor_MissingNativeTableFallsBackToOldApproximation:
// NativeMovementCostRows 沒載入(舊測試 fixture、或資產遺失)時,行為必須完全
// 退回既有的 doc02 approximation,不 panic、不誤判。
func TestMoveCostFor_MissingNativeTableFallsBackToOldApproximation(t *testing.T) {
	st := &State{
		W: 1, H: 1,
		Cost:                   []int{1},
		NativeTerrainMoveCodes: []byte{2}, // 森林
	}
	u := &Unit{ClassID: 1, MoveType: MoveCavalry}
	if got := st.MoveCostFor(u, 0, 0); got != 2 {
		t.Errorf("MoveCostFor(無原生表, 騎兵過森林) = %d, want 2(退回舊 approximation)", got)
	}
}

// TestLoad_ReadsCostFromMapJSON:units.json 同目錄放一份含 "cost" 的 map.json,
// Load 應自動接上;w/h 對不上或缺檔則 Cost 保持 nil(不 fail)。
func TestLoad_ReadsCostFromMapJSON(t *testing.T) {
	dir := t.TempDir()

	unitsPath := filepath.Join(dir, "u.json")
	unitsRaw, _ := json.Marshal(map[string]any{
		"map": 0, "w": 2, "h": 2, "own_deploy": []any{},
		"units": []any{},
	})
	if err := os.WriteFile(unitsPath, unitsRaw, 0644); err != nil {
		t.Fatal(err)
	}
	mapRaw, _ := json.Marshal(map[string]any{
		"w": 2, "h": 2, "tileW": 24, "tileH": 24, "cols": 16,
		"tiles": []int{0, 1, 0, 1}, "cost": []int{1, 2, 99, 1}, "native_composition_event_bytes": []byte{0, 0x40, 0x80, 0},
		"native_field_event_slots": []int{-1, 3, -1, -1},
		"native_field_events": append(
			make([]NativeFieldEvent, 3),
			append([]NativeFieldEvent{{EventID: 82, Selector: 1}}, make([]NativeFieldEvent, 12)...)...,
		),
		"native_tile_blit_modes": []byte{0, 0, 0, 0}, "native_terrain_control": []byte{0, 0, 0, 0, 0, 4, 0, 0},
	})
	if err := os.WriteFile(filepath.Join(dir, "map.json"), mapRaw, 0644); err != nil {
		t.Fatal(err)
	}

	st, err := Load(unitsPath)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	want := []int{1, 2, 99, 1}
	if len(st.Cost) != len(want) {
		t.Fatalf("Cost len = %d, want %d", len(st.Cost), len(want))
	}
	for i, w := range want {
		if st.Cost[i] != w {
			t.Errorf("Cost[%d] = %d, want %d", i, st.Cost[i], w)
		}
	}
	if got := st.MoveCost(0, 1); got != 99 {
		t.Errorf("MoveCost(0,1) = %d, want 99", got)
	}
	if got, want := st.NativeCompositionEventBytes, []byte{0, 0x40, 0x80, 0}; !reflect.DeepEqual(got, want) {
		t.Errorf("NativeCompositionEventBytes=%v want %v", got, want)
	}
	if got, ok := NativeFieldEventIDAt(st, 1, 0, 1); !ok || got != 82 {
		t.Fatalf("NativeFieldEventIDAt=(%d,%v), want (82,true)", got, ok)
	}
	if got, want := st.NativeTileBlitModes, []byte{0xff, 0xff, 0xff, 0xff}; !reflect.DeepEqual(got, want) || !reflect.DeepEqual(st.NativeTerrainControl, []byte{0, 0, 0, 0, 0, 4, 0, 0}) || !reflect.DeepEqual(st.NativeTerrainMoveCodes, []byte{0, 4, 0, 4}) {
		t.Fatalf("Native terrain renderer inputs modes=%v control=%v move codes=%v", got, st.NativeTerrainControl, st.NativeTerrainMoveCodes)
	}
}

// TestLoad_NoMapJSON_CostNil:同目錄沒有 map.json(舊資產或還沒重新匯出)時,
// Load 不應失敗,Cost 保持 nil,MoveCost 退回全平地。
func TestLoad_NoMapJSON_CostNil(t *testing.T) {
	dir := t.TempDir()
	unitsPath := filepath.Join(dir, "u.json")
	unitsRaw, _ := json.Marshal(map[string]any{
		"map": 0, "w": 3, "h": 3, "own_deploy": []any{}, "units": []any{},
	})
	if err := os.WriteFile(unitsPath, unitsRaw, 0644); err != nil {
		t.Fatal(err)
	}
	st, err := Load(unitsPath)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if st.Cost != nil {
		t.Errorf("Cost = %v, want nil(無 map.json)", st.Cost)
	}
	if st.NativeCompositionEventBytes != nil {
		t.Errorf(
			"NativeCompositionEventBytes=%v want nil",
			st.NativeCompositionEventBytes,
		)
	}
	if st.NativeTerrainMoveCodes != nil {
		t.Errorf("NativeTerrainMoveCodes=%v want nil", st.NativeTerrainMoveCodes)
	}
	if got := st.MoveCost(1, 1); got != 1 {
		t.Errorf("MoveCost = %d, want 1", got)
	}
}
