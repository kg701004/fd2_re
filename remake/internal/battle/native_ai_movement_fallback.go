package battle

import "encoding/binary"

// NativeAIMovementFallbackResult reports which fallback branch fired for one
// AI unit with no immediate action available at its current position (the
// 0x14EF0 "nothing to do here" case).
type NativeAIMovementFallbackResult struct {
	Moved       bool
	Rested      bool
	Destination Cell
}

// Native 0x13A9F dispatch mode nibble values (record+0x34 & 0xf). Across all
// 33 shipped maps' AI units with raw provenance (1887 total), the observed
// distribution is 0=1063, 1=34, 2=535, 3=78, 4=34, 5=41, 7=4, 8=90, 9=2,
// 10=6 -- see docs/knowledge-base/11-enemy-ai.md's mode table for each
// mode's dispatch. Modes 0/1/2/3/4/7/8/9/10 are fully implemented; mode 5
// is partially implemented (see ApplyNativeAIMode5MovementFallback).
const (
	NativeAIDispatchMode0  = 0
	NativeAIDispatchMode1  = 1
	NativeAIDispatchMode2  = 2
	NativeAIDispatchMode3  = 3
	NativeAIDispatchMode4  = 4
	NativeAIDispatchMode5  = 5
	NativeAIDispatchMode7  = 7
	NativeAIDispatchMode8  = 8
	NativeAIDispatchMode9  = 9
	NativeAIDispatchMode10 = 10
)

// nativeAIMovementFallbackContext bundles the per-turn native data every
// mode's movement fallback needs, computed once per call so mode-specific
// entry points don't duplicate the same provenance/table lookups.
type nativeAIMovementFallbackContext struct {
	s           *State
	actor       *Unit
	actorIndex  int
	costRow     []byte
	markedFlags []byte
	records     []byte
	selector    int
}

// newNativeAIMovementFallbackContext resolves the shared inputs and applies
// the common gates: raw camp/active provenance, movement/terrain tables, and
// composition flags. It does NOT check the mode nibble -- callers gate that
// themselves so each mode's own "not my mode" rejection stays next to its
// own dispatch logic.
func newNativeAIMovementFallbackContext(s *State, actor *Unit) (nativeAIMovementFallbackContext, bool) {
	var zero nativeAIMovementFallbackContext
	if s == nil || actor == nil || !actor.HasNativeRecordByte6 || !actor.HasNativeRecordByte5 {
		return zero, false
	}
	actorIndex := -1
	for i, u := range s.Units {
		if u == actor {
			actorIndex = i
			break
		}
	}
	if actorIndex < 0 {
		return zero, false
	}
	costRow, ok := s.nativeMovementCostRowFor(actor)
	if !ok || len(s.NativeTerrainMoveCodes) != s.W*s.H {
		return zero, false
	}
	baseFlags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return zero, false
	}
	records, err := NativeAIScoringRecords(s.Units)
	if err != nil {
		return zero, false
	}
	selector := int(actor.NativeRecordByte6)
	// 0x14121 marks the opposing group's cells (0x40) and their neighbours
	// (0x80) via 0x145CD before its own budget-28 flood-fill -- the same
	// preamble NativeAIPhysicalDestinations already performs. Without this,
	// NativePathBlockedCoordinate's search for a 0x40 cell can never match
	// anything, since NativeCommandBaseFlags alone never sets that bit.
	markedFlags, err := nativeAIMarkOpposingGroupFlags(s.W, s.H, records, len(s.Units), selector, baseFlags)
	if err != nil {
		return zero, false
	}
	return nativeAIMovementFallbackContext{
		s: s, actor: actor, actorIndex: actorIndex,
		costRow: costRow, markedFlags: markedFlags, records: records, selector: selector,
	}, true
}

// moveToward reproduces feeding an intended coordinate (from 0x14121 or
// 0x13E9C) into 0x14B78's normal pathing/movement rather than teleporting
// onto it -- 0x14121's own disassembly (00014121) shows the found coordinate
// is a 0x14B78 argument, not a literal destination, so a target cell that's
// occupied or out of movement range is approached, not landed on.
func (ctx nativeAIMovementFallbackContext) moveToward(intended Cell) (Cell, bool) {
	// sortedReachCells (combat.go) fixes Go's randomized map iteration order
	// into a stable (Y,X) scan before this candidate list reaches
	// SelectNativeMovementDestination's first-seen-wins tie-break -- see that
	// function's doc comment for how this was found (a headless full-battle
	// determinism test caught two runs from the same fixed RNG seed
	// diverging here).
	candidates := make([]Cell, 0, ctx.s.W*ctx.s.H)
	for _, c := range sortedReachCells(ctx.s.Reachable(ctx.actor)) {
		if ctx.s.UnitAt(c.X, c.Y) != nil {
			continue
		}
		candidates = append(candidates, c)
	}
	dest, found := SelectNativeMovementDestination(candidates, intended)
	if found {
		ctx.actor.SetMapPlacement(dest.X, dest.Y, ctx.actor.Dir)
	}
	return dest, found
}

// tryBlockedCoordinate attempts 0x14121 (budget 28 blocked-cell search) and
// moves toward its result if found.
func (ctx nativeAIMovementFallbackContext) tryBlockedCoordinate() (NativeAIMovementFallbackResult, bool) {
	intended, found, err := NativePathBlockedCoordinate(
		ctx.s.W, ctx.s.H, Cell{X: ctx.actor.X, Y: ctx.actor.Y}, 28, ctx.markedFlags, ctx.s.NativeTerrainMoveCodes, ctx.costRow,
	)
	if err != nil || !found {
		return NativeAIMovementFallbackResult{}, false
	}
	dest, moved := ctx.moveToward(intended)
	if !moved {
		return NativeAIMovementFallbackResult{}, false
	}
	return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
}

// tryIdleRecovery applies 0x13FD4's raw maxHP/5 recovery if the actor is
// eligible (not poisoned/blocked, not already full HP).
func (ctx nativeAIMovementFallbackContext) tryIdleRecovery() (NativeAIMovementFallbackResult, bool) {
	healed, err := ApplyNativeAIIdleRecovery(ctx.records, len(ctx.s.Units), ctx.actorIndex)
	if err != nil || !healed {
		return NativeAIMovementFallbackResult{}, false
	}
	base := ctx.actorIndex * nativeRecordSize
	ctx.actor.HP = int(binary.LittleEndian.Uint16(ctx.records[base+0x40 : base+0x42]))
	return NativeAIMovementFallbackResult{Rested: true}, true
}

// ApplyNativeAIMovementFallback reproduces native mode 0's fallback chain
// once 0x14EF0 has found no immediate physical/spell/item action worth
// taking at the actor's current position (disassembly-confirmed 2026-08-14,
// Ghidra decompile of the "新版" reference EXE, docs/knowledge-base/11-enemy-ai.md):
//
//	0x14121 (budget 28, 0x4E1A6 mode 2 blocked-cell search) -> found: move toward it
//	else 0x13E9C (nearest raw opposite-selector-group unit) -> found: move toward it
//	else 0x13FD4 (idle HP recovery, maxHP/5 if +0x25/+0x26 both zero)
//
// This reproduces only the MOVEMENT-ONLY slice of mode 0. Deciding whether an
// immediate action is available at the current position (0x14EF0's own
// physical/spell/item scoring and execution) is a separate, much larger
// piece and is NOT reproduced here -- the caller must still make that
// decision with its own existing logic before falling back to this function.
//
// ok=false means the required native data isn't available for this actor or
// state (missing raw provenance, movement tables, or composition flags) --
// the caller should use its own legacy approximation entirely in that case;
// this function never partially applies a result.
//
// Known caveat: SelectNativeNearestOppositeCoordinate's raw selector is
// taken directly from actor.NativeRecordByte6 (the actor's own raw camp),
// not from the two-pass Ally/Enemy scan-order selector 0x1D80B/0x1D8BA
// would supply during a real turn -- reproducing that scan structure is out
// of scope for this movement-only slice.
//
// Gated on actor.NativeRecordByte34&0xf == NativeAIDispatchMode0: applying
// this chain to a unit whose real mode is 1/2/3/4/5/7/8/9/10 would silently
// reproduce the wrong AI, not an approximation of the right one -- those
// units fall through to the caller's legacy logic (ok=false) until their
// own mode gets its own implementation.
func (s *State) ApplyNativeAIMovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode0 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	return ctx.runMode0Chain(), true
}

// runMode0Chain is mode 0's full fallback body (0x14121 -> 0x13E9C ->
// 0x13FD4). Factored out so mode 3 can reuse it verbatim: 0x12C60 returning
// -1 (target identity not found) jumps directly into mode 0's own branch in
// 00013A9F (address 0x13b05, the start of its 0x14121 call) rather than into
// a separate copy of the same logic.
func (ctx nativeAIMovementFallbackContext) runMode0Chain() NativeAIMovementFallbackResult {
	if result, done := ctx.tryBlockedCoordinate(); done {
		return result
	}
	if intended, found, err := SelectNativeNearestOppositeCoordinate(ctx.records, len(ctx.s.Units), ctx.actorIndex, ctx.selector); err == nil && found {
		if dest, moved := ctx.moveToward(intended); moved {
			return NativeAIMovementFallbackResult{Moved: true, Destination: dest}
		}
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result
	}
	return NativeAIMovementFallbackResult{}
}

// ApplyNativeAIMode1MovementFallback reproduces native mode 1's fallback
// chain (disassembly-confirmed 2026-08-14, same 00013A9F dispatcher as mode
// 0): 0x14EF0 has already found no immediate action, so this tries
//
//	0x14121 (budget 28 blocked-cell search) -> found: move toward it
//	else 0x13FD4 (idle HP recovery)
//
// Mode 1 is mode 0's chain with the middle 0x13E9C "nearest opposite unit"
// step removed entirely -- confirmed directly from 00013A9F's mode-1 branch
// (0x13b26-0x13b46), which jumps straight from the 0x14121 call to the same
// shared tail mode 0 uses after its own 0x13E9C attempt, never calling
// 0x13E9C itself. See ApplyNativeAIMovementFallback's doc comment for the
// shared caveats (movement-only scope, raw selector, indirection through
// moveToward instead of a literal destination).
func (s *State) ApplyNativeAIMode1MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode1 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	if result, done := ctx.tryBlockedCoordinate(); done {
		return result, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// ApplyNativeAIMode2MovementFallback reproduces native mode 2's fallback
// chain (disassembly-confirmed 2026-08-14, same 00013A9F dispatcher; see
// also docs/knowledge-base/11-enemy-ai.md's mode table, already-confirmed in
// a prior session): after 0x14EF0 finds no immediate action, mode 2 calls
// 0x14237(actor,moveTarget) instead of 0x14121 -- a different call shape
// than 0x14237's usual per-cell target-enumeration role, and one that
// always returns 0 in this position. There is no 0x14121 blocked-cell
// search and no 0x13E9C nearest-opposite fallback in mode 2 at all: it goes
// straight to the shared tail's 0x13FD4 idle recovery every time 0x14EF0
// fails. So this reproduces only:
//
//	0x13FD4 (idle HP recovery)
//
// Never a move. See ApplyNativeAIMovementFallback's doc comment for the
// shared caveats.
func (s *State) ApplyNativeAIMode2MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode2 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// nativeAIFindActiveUnitByIdentity reproduces 0x12C60(searchIdentity): scan
// the roster in order for the first unit whose record+8 raw identity byte
// equals searchIdentity AND whose record+5 bit0 ("active", the same gate
// used throughout this file) is clear -- confirmed via 0x34894, the raw
// `record+5 & 1` helper 0x12C60 calls per candidate. Returns (-1, false) if
// none qualifies; 0x12C60 does check a second roster/table when the primary
// scan finds no byte+8 match at all, but that branch never returns a usable
// index for this caller, so it is not reproduced here.
func nativeAIFindActiveUnitByIdentity(records []byte, count int, searchIdentity byte) (int, bool) {
	for unit := 0; unit < count; unit++ {
		record := records[unit*nativeRecordSize:]
		if record[8] == searchIdentity && record[5]&1 == 0 {
			return unit, true
		}
	}
	return -1, false
}

// ApplyNativeAIMode3MovementFallback reproduces native mode 3's fallback
// chain (disassembly-confirmed 2026-08-14, same 00013A9F dispatcher): after
// 0x14EF0 finds no immediate action, mode 3 looks up a specific unit by the
// raw identity stored at record+0x35 via 0x12C60:
//
//	found -> move toward that unit's raw position (via 0x14B78, same
//	         moveToward indirection as every other mode here) -> if that
//	         movement itself fails, 0x13FD4 idle recovery
//	not found -> falls straight into mode 0's OWN branch (address 0x13b05,
//	             confirmed by direct disassembly of the JZ target) -- i.e.
//	             the complete mode 0 chain (0x14121 -> 0x13E9C -> 0x13FD4),
//	             not a separate approximation of it
//
// See ApplyNativeAIMovementFallback's doc comment for the shared caveats.
func (s *State) ApplyNativeAIMode3MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode3 ||
		!actor.HasNativeRecordByte35 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	targetIndex, found := nativeAIFindActiveUnitByIdentity(ctx.records, len(s.Units), actor.NativeRecordByte35)
	if !found {
		return ctx.runMode0Chain(), true
	}
	targetRecord := ctx.records[targetIndex*nativeRecordSize:]
	intended := Cell{X: int(targetRecord[0]), Y: int(targetRecord[1])}
	if dest, moved := ctx.moveToward(intended); moved {
		return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// ApplyNativeAIMode8MovementFallback reproduces native mode 8's fallback
// (disassembly-confirmed 2026-08-14, same 00013A9F dispatcher): once
// 0x14EF0 finds no immediate action, mode 8 does nothing at all -- no
// 0x14121 search, no 0x13E9C nearest-opposite lookup, no 0x13FD4 idle
// recovery. Its dispatch case (`CMP EAX,0x8; JZ 0x1317d`) jumps straight to
// a shared epilogue at an address that at first looks like it belongs to an
// unrelated function (FUN_0001300d); it is legitimate, not a disassembly
// error -- both functions push the identical 4-register/0xc-local frame
// shape (`PUSH EBX,ESI,EDI,EBP; SUB ESP,0xc` in 00013A9F's own prologue
// exactly matches 0001300D's), so the compiler tail-merged their otherwise
// byte-identical epilogues into one shared block. A raw capstone
// cross-check against the local FD2.EXE produced garbage at this address
// due to an unrelated base-address bug in disasm_le.py's "range"/"dis"
// commands (confirmed by it also failing at the already-known-good 0x13A9F
// function entry) -- that was a tooling artifact, not evidence against this
// reading.
//
// So this returns success (ok=true) with an EMPTY result whenever mode 8
// applies: unlike every other mode here, "correctly reproduced" for mode 8
// means taking no action, not falling through to the caller's legacy
// approximation (which would incorrectly make the unit chase the nearest
// enemy). The caller must treat (zero result, ok=true) as "do nothing," not
// as "native data unavailable."
func (s *State) ApplyNativeAIMode8MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode8 {
		return zero, false
	}
	return zero, true
}

// moveTowardFixedRecordCoordinate is shared by modes 4/7/10: move toward the
// fixed map coordinate stored at record+0x35 (X) / record+0x36 (Y), via the
// same moveToward indirection as every other mode (0x14B78's normal
// pathing, not a literal teleport).
func (ctx nativeAIMovementFallbackContext) moveTowardFixedRecordCoordinate() (Cell, bool) {
	intended := Cell{X: int(ctx.actor.NativeRecordByte35), Y: int(ctx.actor.NativeRecordByte36)}
	return ctx.moveToward(intended)
}

// ApplyNativeAIMode4MovementFallback reproduces native mode 4 (disassembly-
// confirmed 2026-08-14, cross-verified against docs/knowledge-base/11-enemy-ai.md's
// already-recorded mode table): unlike every other mode, mode 4 never calls
// 0x14EF0 at all -- it unconditionally hands (record+0x35, record+0x36) to
// 0x14B78 as a fixed destination coordinate. Manually traced from
// 00013A9F's mode-4 branch (0x13bdc-0x13c19): the push order
// (EDI=selector, ESI=actor, [ESP+8]=record+0x36, [ESP+0x10]=record+0x35)
// matches 0x14B78(X,Y,actor,selector)'s established argument order with X
// pushed last, giving X=record+0x35, Y=record+0x36 -- confirmed by doc11's
// independent one-line summary ("直接以 +0x35/+0x36 為目的座標交給
// 0x14B78"). If the move itself fails, falls through to 0x13FD4 idle
// recovery via the same shared tail every other mode uses.
//
// This function is slotted into the same "runs after the caller's own
// immediate-action check" position as every other mode here for
// consistency, even though the real 0x14EF0 gate never exists for mode 4 --
// since 0x14EF0 itself isn't reproduced by ANY of these functions, this
// doesn't change what's actually approximated.
func (s *State) ApplyNativeAIMode4MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode4 ||
		!actor.HasNativeRecordByte35 || !actor.HasNativeRecordByte36 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	if dest, moved := ctx.moveTowardFixedRecordCoordinate(); moved {
		return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// ApplyNativeAIMode7MovementFallback reproduces native mode 7 (disassembly-
// confirmed 2026-08-14; doc11: "直接移向 +0x35/+0x36；抵達後呼叫
// 0x32975，其已知效果僅是整個 record+5 寫成 1"): moves toward the fixed
// (record+0x35, record+0x36) coordinate exactly like mode 4, but when the
// unit lands EXACTLY on that coordinate (not merely as close as the
// movement budget allowed), it becomes inactive -- record+5 is written to
// 1, which sets bit0, the same "active" gate every mode here already
// checks. This reproduces that as a full overwrite (record+5=1), matching
// 0x32975's confirmed effect precisely rather than only setting bit0 and
// guessing at the rest of the byte.
func (s *State) ApplyNativeAIMode7MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode7 ||
		!actor.HasNativeRecordByte35 || !actor.HasNativeRecordByte36 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	intended := Cell{X: int(actor.NativeRecordByte35), Y: int(actor.NativeRecordByte36)}
	dest, moved := ctx.moveTowardFixedRecordCoordinate()
	if moved && dest == intended {
		actor.NativeRecordByte5 = 1
	}
	if moved {
		return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// ApplyNativeAIMode9MovementFallback reproduces native mode 9 (disassembly-
// confirmed 2026-08-14; doc11: "以 +0x35 找單位並移向其座標；找不到時回到
// 一般 0x14EF0 路線"): looks up an active unit by the identity stored at
// record+0x35 via the same 0x12C60 helper as mode 3, and moves toward it if
// found. Unlike mode 3, a failed lookup does NOT fall into mode 0's chain --
// it falls back to the general 0x14EF0 route, which this file doesn't
// reproduce (see every other mode's doc comment). So an identity miss here
// returns ok=false, deferring entirely to the caller's own legacy logic,
// rather than guessing at a movement action mode 9 never takes in this
// case.
func (s *State) ApplyNativeAIMode9MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode9 ||
		!actor.HasNativeRecordByte35 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	targetIndex, found := nativeAIFindActiveUnitByIdentity(ctx.records, len(s.Units), actor.NativeRecordByte35)
	if !found {
		return zero, false
	}
	targetRecord := ctx.records[targetIndex*nativeRecordSize:]
	intended := Cell{X: int(targetRecord[0]), Y: int(targetRecord[1])}
	if dest, moved := ctx.moveToward(intended); moved {
		return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// ApplyNativeAIMode10MovementFallback reproduces native mode 10
// (disassembly-confirmed 2026-08-14; doc11: "先走 0x14EF0；失敗改移向
// +0x35/+0x36"): once the caller's own immediate-action check has already
// failed, mode 10's fallback is identical to mode 4/7's movement (move
// toward the fixed record+0x35/+0x36 coordinate), just without mode 7's
// arrival deactivation.
func (s *State) ApplyNativeAIMode10MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode10 ||
		!actor.HasNativeRecordByte35 || !actor.HasNativeRecordByte36 {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	if dest, moved := ctx.moveTowardFixedRecordCoordinate(); moved {
		return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// ApplyNativeAIMode5MovementFallback reproduces PART of native mode 5
// (disassembly-confirmed 2026-08-14 against the live "新版" reference EXE at
// its own true addresses -- see the address-instability note below): after
// 0x14EF0 finds no immediate action, mode 5 checks whether the event keyed
// by record+0x3D has already fired, via the raw battle-local flag array at
// [0x53AD5] (State.NativeEventState, an existing 0x20-byte reproduction --
// see doc25/model.go's own note that 0x13d00, mode 5's own consumed-flag
// write, already writes into this table):
//
//	NativeEventState[record+0x3D] != 0 (already consumed) ->
//	    0x14121 (budget 28 blocked-cell search) -> found: move toward it
//	    else 0x13FD4 (idle HP recovery)
//	    -- structurally IDENTICAL to mode 1's own fallback body (0x13a9f's
//	       mode-5 branch jumps to the exact same 0x13b05 tail mode 1 uses)
//	== 0 (not yet consumed) ->
//	    0x15DF3(record+0x3D, &coord) scans the map's FDSHAP-derived cell
//	    table for the (x,y) whose terrain-control flags read `&0x60==0x20`
//	    (the same treasure/hidden-item gate doc25 §"低5位欄位...寶箱" already
//	    named) and whose embedded value equals record+0x3D, then moves there;
//	    on EXACT arrival it reads a 3-byte-stride record at
//	    [0x53a55+0x53+event_id*3] (kind byte, word value), conditionally
//	    writes record+0x31/+0x32 (State's own NativeRecordDeathEffect
//	    storage) and grants an item via 0x1BB8C (AssignNativeReservedItem)
//	    when kind==0, marks the event consumed, and sets record+0x34=7 (the
//	    unit permanently becomes a mode-7 unit, which -- since it's already
//	    standing on the target coordinate -- will deactivate on its very next
//	    evaluation via ApplyNativeAIMode7MovementFallback's arrival check).
//
// Both branches are reproduced. The "not yet consumed" branch's target
// coordinate comes from State.Treasures (model.go's loadTreasures): that map
// was already built at Load time by joining each map's per-cell
// treasure_slots/treasure_hidden (tools/sync_native_treasures.py, the exact
// "&0x60!=0" FDSHAP terrain-control gate doc25 describes, bit 0x40 = hidden)
// against the control segment's 16-slot chest kind/value table (f.Chests,
// the same [0x53a55+0x53+id*3] records parse_field.py already extracts as
// "chests") -- this is the identical data 0x15DF3's scan reproduces, it was
// just never connected to this dispatch mode before. Finding the cell is a
// plain scan for the Treasure whose Slot equals record+0x3D (the "embedded
// value equals event_id" gate); OpenedTreasure is NOT consulted here since
// that flag tracks the separate player-facing claim state ClaimTreasure
// uses, not this mode's own NativeEventState gate already checked above.
//
// Address-instability note: 0x12D7B and 0x15DF3 are OLD-reference-EXE
// (357074-byte, now lost from the user's machine) linear addresses recorded
// in docs/data/fd2_ai_mode_dispatch_disasm.txt. Naively reusing those same
// numbers against the current 509158-byte "新版" reference EXE is WRONG --
// confirmed by direct byte-pattern search: the dispatcher's own
// `push 0x30; call ...; push ebx,esi,edi,ebp; sub esp,0xc` prologue is at
// linear 0x38CBD in the new EXE, not 0x13A9F, and the shift is NOT a single
// constant across the whole module (delta 0x25114 at the entry point vs
// 0x25214 at its first callee, a 0x100 discrepancy) -- code was inserted
// unevenly between old and new builds, so old-doc addresses cannot be
// ported to the new EXE by adding one offset. The two callees this mode
// needs were re-located by disassembling the dispatcher fresh at its real
// 0x38CBD entry and reading the actual (not delta-guessed) call targets at
// the structurally-identical positions: 0x12D7B -> 0x37F8F (confirmed a
// harmless "reset pathing origin to the actor's own current position" call
// with no observable game-state effect, safe to omit here exactly as the
// mode 3/4/7/9 implementations already omit it), 0x15DF3 -> 0x3B007
// (confirmed the FDSHAP grid scan described above). This does not affect
// any other already-shipped mode: those were derived entirely from the
// self-consistent old-EXE dump file and cross-checked against doc11's
// independently-written mode table, never by porting an old address into a
// live new-EXE disassembly.
func (s *State) ApplyNativeAIMode5MovementFallback(actor *Unit) (NativeAIMovementFallbackResult, bool) {
	var zero NativeAIMovementFallbackResult
	if actor == nil || !actor.HasNativeRecordByte34 || actor.NativeRecordByte34&0xf != NativeAIDispatchMode5 ||
		!actor.HasNativeRecordByte3D {
		return zero, false
	}
	if int(actor.NativeRecordByte3D) >= len(s.NativeEventState) {
		return zero, false
	}
	ctx, ok := newNativeAIMovementFallbackContext(s, actor)
	if !ok {
		return zero, false
	}
	if s.NativeEventState[actor.NativeRecordByte3D] == 0 {
		target, found := s.nativeMode5TreasureTargetCell(int(actor.NativeRecordByte3D))
		if !found {
			// No map data claims this event id as a treasure cell -- either
			// this map genuinely has no such event (nothing to reproduce) or
			// the source data is incomplete. Fail closed rather than guess.
			return zero, false
		}
		if dest, moved := ctx.moveToward(target); moved {
			return NativeAIMovementFallbackResult{Moved: true, Destination: dest}, true
		}
		return NativeAIMovementFallbackResult{}, true
	}
	if result, done := ctx.tryBlockedCoordinate(); done {
		return result, true
	}
	if result, done := ctx.tryIdleRecovery(); done {
		return result, true
	}
	return NativeAIMovementFallbackResult{}, true
}

// nativeMode5TreasureTargetCell finds the map cell whose Treasure.Slot
// equals the given event id -- the reproduction of 0x15DF3's grid scan,
// backed by State.Treasures (see the doc comment above). At most one cell
// should ever match a given slot per map (the reserved 16-slot chest table
// is one entry per slot); a plain scan is the same "double loop over the
// grid" the disassembly itself performs.
func (s *State) nativeMode5TreasureTargetCell(eventID int) (Cell, bool) {
	for cell, treasure := range s.Treasures {
		if treasure.Slot == eventID {
			return cell, true
		}
	}
	return Cell{}, false
}
