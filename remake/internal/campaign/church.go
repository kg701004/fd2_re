package campaign

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

var classNames = []string{"龍", "劍士", "戰士", "騎士", "弓兵", "法師", "僧侶", "盜賊", "武者", "劍聖", "聖戰士", "聖騎士", "狙擊手", "大法師", "祭師", "龍劍士", "鬥士", "英雄", "魔戰士", "龍騎士", "神射手", "召喚師", "聖者", "忍者", "武聖", "機兵", "？？？"}

// AdvanceNativeChurchServiceSelection mirrors 0x2d7bd's four-entry service
// cursor. The native selector reacts to left (raw scancode 75) and right
// (raw scancode 77), wrapping 0..3; it does not use the up/down movement
// contract of the party/character lists. Keep the operation pure so the UI
// can share the recovered ABI without assigning names to the four services.
func AdvanceNativeChurchServiceSelection(current, delta int) int {
	if current < 0 || current > 3 {
		current = 0
	}
	if delta < 0 {
		delta = -1
	} else if delta > 0 {
		delta = 1
	} else {
		return current
	}
	current += delta
	if current < 0 {
		return 3
	}
	if current > 3 {
		return 0
	}
	return current
}

// AdvanceNativeClassConfirmation mirrors 0x19953's two-choice prompt:
// left selects zero and right selects one. There is no wrap or up/down path.
func AdvanceNativeClassConfirmation(current, horizontal int) int {
	if current != 0 && current != 1 {
		current = 0
	}
	if horizontal < 0 {
		return 0
	}
	if horizontal > 0 {
		return 1
	}
	return current
}

// NativeClassCandidateWindow mirrors 0x311DC's three-row viewport. The
// selection is bounded by the caller; once it moves below the third visible
// row, the window follows it one row at a time.
func NativeClassCandidateWindow(count, selected int) (start, visible int) {
	if count <= 0 || selected < 0 || selected >= count {
		return 0, 0
	}
	start = selected - 2
	if start < 0 {
		start = 0
	}
	visible = count - start
	if visible > 3 {
		visible = 3
	}
	return start, visible
}

// AdvanceNativeTwoColumnSelection mirrors the bounded list movement used by
// 0x2e6b8/0x2df6b. delta is one of -2,-1,+1,+2 (left/up/right/down); invalid
// counts or moves leave the cursor unchanged, and there is no wrap.
func AdvanceNativeTwoColumnSelection(current, count, delta int) int {
	if count <= 0 {
		return 0
	}
	if current < 0 {
		return 0
	}
	if current >= count {
		return count - 1
	}
	if delta != -2 && delta != -1 && delta != 1 && delta != 2 {
		return current
	}
	next := current + delta
	if next < 0 || next >= count {
		return current
	}
	return next
}

// ClassName is the EXE mechanical class-name table used by target class IDs.
func ClassName(classID int) string {
	if classID >= 0 && classID < len(classNames) {
		return classNames[classID]
	}
	return fmt.Sprintf("職業%d", classID)
}

// ClassChangeGrowth is one 11-byte EXE growth row (0x4e4d1).  The five
// pairs are encoded as [min,max), matching 0x1e529's idiv(max-min) path.
type ClassChangeGrowth struct {
	AP, DP, DX, HP, MP [2]int
}

func rollClassChangeRange(r [2]int, rng *rand.Rand) (int, error) {
	if r[1] < r[0] {
		return 0, fmt.Errorf("class change: invalid range [%d,%d)", r[0], r[1])
	}
	if r[1] == r[0] {
		return r[0], nil
	}
	if rng == nil {
		return 0, fmt.Errorf("class change: missing rng")
	}
	return r[0] + rng.Intn(r[1]-r[0]), nil
}

// ApplyClassChange mirrors the proven 0x31602 state writes.  0x1e529 adds the
// rolled row value to the existing raw AP/DP/DX/MaxHP/MaxMP words; it does not
// replace them. The native routine leaves the level byte untouched and clears
// EXP, then copies the new maxima to current HP/MP. The caller owns the
// editable class-name lookup and subsequent 0x1b750-equivalent equipment
// recomputation. removeItemIndex is the compact Inventory index returned by
// the church item scan, or -1 when this branch consumed no item.
func ApplyClassChange(u *battle.Unit, targetPortrait, classID, growthGroup int, row ClassChangeGrowth, rng *rand.Rand, removeItemIndex int) error {
	if u == nil {
		return fmt.Errorf("class change: missing unit")
	}
	if targetPortrait < 0 || targetPortrait > 0xff || classID < 0 || classID > 0xff || growthGroup < 0 || growthGroup > 0xff {
		return fmt.Errorf("class change: invalid target/class/group")
	}
	if removeItemIndex >= len(u.Inventory) || removeItemIndex < -1 {
		return fmt.Errorf("class change: invalid item index")
	}
	ap, err := rollClassChangeRange(row.AP, rng)
	if err != nil {
		return err
	}
	dp, err := rollClassChangeRange(row.DP, rng)
	if err != nil {
		return err
	}
	dx, err := rollClassChangeRange(row.DX, rng)
	if err != nil {
		return err
	}
	hp, err := rollClassChangeRange(row.HP, rng)
	if err != nil {
		return err
	}
	mp, err := rollClassChangeRange(row.MP, rng)
	if err != nil {
		return err
	}
	if removeItemIndex >= 0 && !u.RemoveInventoryIndex(removeItemIndex) {
		return fmt.Errorf("class change: item removal failed")
	}
	u.AP += ap
	u.DP += dp
	u.DX += dx
	u.MaxHP += hp
	u.MaxMP += mp
	u.HP = u.MaxHP
	u.MP = u.MaxMP
	// The second byte returned by 0x4e48d is the class mobility increment;
	// native unit+0x3b is the movement budget used by pathfinding.
	u.MV += growthGroup
	u.Exp = 0
	u.Portrait, u.ClassID = targetPortrait, classID
	// 0x31571..0x3157a rewrites raw +0x20 and +7, but not +0x1f.
	u.NativeRecordClass, u.HasNativeRecordClass = byte(classID), true
	// Native class-change flow 0x31576..0x3157a writes the resolved target
	// byte to live unit+7. For player construction that byte is both the
	// FIGANI selector and the next 0x11019 raw map key; stable Fig remains the
	// JOIN/+8 identity. A previous cache slot belongs to the old key.
	u.BattleFig = targetPortrait
	u.MapSelectorKey, u.HasMapSelectorKey = targetPortrait, true
	u.MapSelectorSlot, u.HasMapSelectorSlot = 0, false
	u.NativeMapPresentation, u.HasNativeMapPresentation = battle.NativeMapPresentationState{}, false
	return nil
}

type reviveFeeTable struct {
	Rates []int `json:"rates"`
}

// LoadReviveFeeRates loads the direct EXE-derived class fee words. The source
// field is intentionally documentation-only; callers receive an indexed copy.
func LoadReviveFeeRates(path string) ([]int, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var table reviveFeeTable
	if err := json.Unmarshal(raw, &table); err != nil {
		return nil, err
	}
	if len(table.Rates) == 0 {
		return nil, fmt.Errorf("revive fee table is empty")
	}
	return append([]int(nil), table.Rates...), nil
}

// CanChangeClass is the proven 0x31793 candidate predicate. The native
// routine uses the roster record's level and portrait byte; it does not list
// already promoted portrait groups (>=0x12) or portrait 7.
func CanChangeClass(u *battle.Unit) bool {
	return u != nil && u.Lv >= 20 && u.Portrait < 0x12 && u.Portrait != 7
}

// ClassChangeCandidates preserves caller order (normally JOIN chronology).
func ClassChangeCandidates(roster map[int]battle.Unit, order []int) []int {
	out := make([]int, 0)
	seen := make(map[int]bool, len(roster))
	for _, id := range order {
		if seen[id] {
			continue
		}
		seen[id] = true
		u, ok := roster[id]
		if ok && CanChangeClass(&u) {
			out = append(out, id)
		}
	}
	for id, u := range roster {
		if !seen[id] && CanChangeClass(&u) {
			out = append(out, id)
		}
	}
	return out
}

// CanRevive matches the original church candidate filter: the character must
// have a valid max HP and currently be dead/inactive. The native handler's
// 0x309ff list is built from roster records, not from the active battle array.
func CanRevive(u *battle.Unit) bool {
	return u != nil && u.MaxHP > 0 && u.HP <= 0
}

// ReviveUnit applies the proven 0x30dc3 write-back sequence. feeRate is the
// original class fee word loaded from the editable class-fee table; keeping it
// as an argument prevents the engine from inventing values until that table is
// exported. Native cost is feeRate * unit level, checked before any mutation.
func ReviveUnit(gold int, u *battle.Unit, feeRate int) (int, int, error) {
	if u == nil {
		return gold, 0, fmt.Errorf("revive: missing unit")
	}
	if !CanRevive(u) {
		return gold, 0, fmt.Errorf("revive: unit is not a candidate")
	}
	if feeRate < 0 {
		return gold, 0, fmt.Errorf("revive: invalid fee rate")
	}
	level := u.Lv
	if level < 1 {
		level = 1
	}
	cost := feeRate * level
	if gold < cost {
		return gold, cost, fmt.Errorf("revive: insufficient gold")
	}
	gold -= cost
	// 0x30f9c clears the raw death/inactive bit; 0x30fa0 copies max HP to
	// current HP. OnField is retained as the remake projection.
	u.RestoreNativeHP()
	u.OnField = true
	return gold, cost, nil
}
