package battle

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

// 驗證序章 units.json 正確載入(M1-8 headless 回歸雛形)。
func TestLoadSerial0(t *testing.T) {
	st, err := Load("../../assets/map0_units.json")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if st.W != 24 || st.H != 24 {
		t.Errorf("size = %dx%d, want 24x24", st.W, st.H)
	}
	if len(st.Units) != 30 {
		t.Errorf("units = %d, want 30", len(st.Units))
	}
	own, ally, enemy := st.AliveCount(Own), st.AliveCount(Ally), st.AliveCount(Enemy)
	t.Logf("own=%d ally=%d enemy=%d deploy=%d turn=%d", own, ally, enemy, len(st.OwnDeploy), st.Turn)
	if own < 1 || enemy < 1 {
		t.Errorf("缺陣營:own=%d enemy=%d", own, enemy)
	}
	if st.Turn != 1 {
		t.Errorf("初始回合 = %d, want 1", st.Turn)
	}
	for _, u := range st.Units {
		if u.HP <= 0 || u.MaxHP <= 0 {
			t.Errorf("%s 單位 HP 異常:%d/%d", u.Camp, u.HP, u.MaxHP)
		}
		if u.MV <= 0 {
			t.Errorf("%s 單位移動力 = %d", u.Camp, u.MV)
		}
		// 註:own 不再自動塞部署格(部署格保留給 scenario spawn_party 主角隊,
		// 見 Load 內註解);units.json 的 own 沿用檔案座標,不驗部署格。
	}
	// UnitAt + Alive
	u0 := st.Units[0]
	if got := st.UnitAt(u0.X, u0.Y); got == nil {
		t.Errorf("UnitAt(%d,%d) = nil", u0.X, u0.Y)
	}
	u0.HP = 0
	if st.UnitAt(u0.X, u0.Y) == u0 {
		t.Error("陣亡單位不應被 UnitAt 回傳")
	}
}

func TestLoadKeepsBattleFigSeparateFromLegacyMapFig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "units.json")
	if err := os.WriteFile(path, []byte(`{"w":1,"h":1,"units":[{"camp":"own","hp":1,"mp":0,"fig":7,"battle_fig":23,"map_selector_key":2,"map_selector_slot":0,"portrait":23,"x":0,"y":0}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	st, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := st.Units[0]; got.Fig != 7 || got.BattleFig != 23 {
		t.Fatalf("selectors = map %d battle %d, want 7/23", got.Fig, got.BattleFig)
	}
	if got := st.Units[0]; !got.HasMapSelectorSlot || got.MapSelectorSlot != 0 {
		t.Fatalf("native map selector=%d known=%v, want slot 0", got.MapSelectorSlot, got.HasMapSelectorSlot)
	}
	if got := st.Units[0]; !got.HasMapSelectorKey || got.MapSelectorKey != 2 {
		t.Fatalf("native map key=%d known=%v, want 2", got.MapSelectorKey, got.HasMapSelectorKey)
	}

	if err := os.WriteFile(path, []byte(`{"w":1,"h":1,"units":[{"camp":"own","hp":1,"mp":0,"fig":7,"portrait":23,"x":0,"y":0}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	st, err = Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := st.Units[0].BattleFig; got != 7 {
		t.Fatalf("legacy BattleFig=%d, want fallback 7", got)
	}
}

func TestLoadPreservesNativeConstructorRawTable(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "units.json")
	raw := `{"w":1,"h":1,"units":[{"camp":"own","hp":1,"mp":0,"fig":7,"portrait":68,"x":0,"y":0,"native_identity":68,"native_constructor":{"branch":"high_class","index":0,"record":[1,2,3,4,5,6,7,8,9,10]}}]}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}
	st, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	got := st.Units[0].NativeConstructor
	if got == nil || got.Branch != "high_class" || got.Index != 0 || len(got.Record) != 10 || got.Record[0] != 1 || got.Record[9] != 10 {
		t.Fatalf("native constructor=%#v", got)
	}
	if !st.Units[0].HasNativeIdentity || st.Units[0].NativeIdentity != 68 {
		t.Fatalf("native identity=%d known=%v", st.Units[0].NativeIdentity, st.Units[0].HasNativeIdentity)
	}
	bad := `{"w":1,"h":1,"units":[{"camp":"own","hp":1,"native_constructor":{"branch":"high_class","index":0,"record":[1]}}]}`
	if err := os.WriteFile(path, []byte(bad), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("malformed native constructor must fail closed")
	}
}

func TestLoadRejectsNativeIdentityOutsideByte(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "units.json")
	if err := os.WriteFile(path, []byte(`{"w":1,"h":1,"units":[{"camp":"own","hp":1,"native_identity":256}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("native identity outside byte must fail closed")
	}
}

func TestMaterializeNativeMapSelectorSlotsRequiresExplicitKeys(t *testing.T) {
	units := []*Unit{
		{MapSelectorKey: 2, HasMapSelectorKey: true},
		{MapSelectorKey: 0, HasMapSelectorKey: true},
		{MapSelectorKey: 2, HasMapSelectorKey: true},
	}
	cache := &fdicon.NativeSelectorCache{}
	if err := MaterializeNativeMapSelectorSlots(units, cache); err != nil {
		t.Fatal(err)
	}
	for i, want := range []int{0, 1, 0} {
		if !units[i].HasMapSelectorSlot || units[i].MapSelectorSlot != want {
			t.Fatalf("unit %d native slot=%d known=%v, want %d", i, units[i].MapSelectorSlot, units[i].HasMapSelectorSlot, want)
		}
	}
	missing := []*Unit{{Fig: 99}}
	if err := MaterializeNativeMapSelectorSlots(missing, &fdicon.NativeSelectorCache{}); err == nil {
		t.Fatal("missing raw key must fail rather than fall back to Fig")
	}
	if missing[0].HasMapSelectorSlot {
		t.Fatal("failed materialization must not mutate slots")
	}
	invalid := []*Unit{
		{MapSelectorKey: 9, HasMapSelectorKey: true},
		{MapSelectorKey: 0x100, HasMapSelectorKey: true},
	}
	cache = &fdicon.NativeSelectorCache{}
	if err := MaterializeNativeMapSelectorSlots(invalid, cache); err == nil {
		t.Fatal("invalid raw key must fail")
	}
	if _, err := cache.KeyForSlot(0); err == nil {
		t.Fatal("preflight failure must not mutate cache")
	}
}

func TestStateNativeMapSelectorCachePreservesConstructionOrder(t *testing.T) {
	st := &State{}
	party := []*Unit{
		{MapSelectorKey: 9, HasMapSelectorKey: true},
		{MapSelectorKey: 4, HasMapSelectorKey: true},
	}
	if err := st.AppendNativeMapSelectorBatch(party); err != nil {
		t.Fatal(err)
	}
	scripted := []*Unit{
		{MapSelectorKey: 0, HasMapSelectorKey: true},
		{MapSelectorKey: 2, HasMapSelectorKey: true},
		{MapSelectorKey: 0, HasMapSelectorKey: true},
	}
	if err := st.AppendNativeMapSelectorBatch(scripted); err != nil {
		t.Fatal(err)
	}
	for i, want := range []int{0, 1, 2, 3, 2} {
		if st.Units[i].MapSelectorSlot != want {
			t.Fatalf("construction slot %d=%d, want %d", i, st.Units[i].MapSelectorSlot, want)
		}
	}
	if err := st.AppendNativeMapSelectorBatch([]*Unit{{Fig: 123}}); err == nil {
		t.Fatal("missing raw key must reject whole append")
	}
	if len(st.Units) != 5 {
		t.Fatalf("failed append mutated unit order: %d", len(st.Units))
	}
	if _, err := st.NativeMapSelectorCache.KeyForSlot(4); err == nil {
		t.Fatal("failed append mutated native cache")
	}
}

func TestNativeMapSpriteKeyFailsClosedAfterLegacyFallback(t *testing.T) {
	st := &State{}
	valid := []*Unit{{MapSelectorKey: 7, HasMapSelectorKey: true}}
	st.AppendNativeMapSelectorBatchOrLegacy(valid)
	if got, ok := st.NativeMapSpriteKey(valid[0]); !ok || got != 7 {
		t.Fatalf("native map key=(%d,%v), want (7,true)", got, ok)
	}
	invalid := []*Unit{{Fig: 99}}
	st.AppendNativeMapSelectorBatchOrLegacy(invalid)
	if st.NativeMapSelectorError == nil {
		t.Fatal("malformed batch did not record native selector failure")
	}
	if _, ok := st.NativeMapSpriteKey(valid[0]); ok {
		t.Fatal("prior native slot remained enabled after malformed fallback")
	}
	if len(st.Units) != 2 || st.Units[1] != invalid[0] {
		t.Fatalf("legacy fallback did not preserve unit order: %#v", st.Units)
	}
}
