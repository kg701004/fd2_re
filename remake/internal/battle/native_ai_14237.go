package battle

import (
	"encoding/binary"
	"fmt"
)

// nativeAIPhysicalTerrainPercentApplies reproduces the gate 0x14237 evaluates
// per unit (disassembly-confirmed 2026-08-14, new-exe address 0x44397, called
// once for the actor and once for each target) before applying the terrain
// percentage adjustment: class 0x13 or race in {4,5}. This is the same raw
// formula as nativeMovementRow19Predicate (move.go's reproduction of the
// old-doc-labelled "0x1F183"), confirmed independently from a completely
// separate disassembly pass -- strong evidence both addresses are the same
// function surviving the old/new edition's code shift. record+0x7 is
// deliberately omitted for the same reason move.go's version omits it: no
// export pipeline populates that byte yet, and omitting only narrows how
// often this gate fires rather than risking a wrong guess.
func nativeAIPhysicalTerrainPercentApplies(record []byte) bool {
	return record[0x20] == 0x13 || record[0x1f] == 4 || record[0x1f] == 5
}

// nativeAIAdjustedTerrainWords applies NativeTerrainAPDPPct to (ap, dp) for a
// unit standing at (x,y), gated by nativeAIPhysicalTerrainPercentApplies --
// when the gate is false or the terrain code is unrecognised,
// 0x14237 leaves the words unadjusted (that's the disassembled control flow:
// the adjustment block is skipped entirely, not zeroed).
func nativeAIAdjustedTerrainWords(record []byte, w, h int, terrainMoveCodes []byte, x, y, ap, dp int) (int, int) {
	if !nativeAIPhysicalTerrainPercentApplies(record) {
		return ap, dp
	}
	if x < 0 || y < 0 || x >= w || y >= h || len(terrainMoveCodes) != w*h {
		return ap, dp
	}
	apPct, dpPct, ok := NativeTerrainAPDPPct(terrainMoveCodes[y*w+x])
	if !ok {
		return ap, dp
	}
	return ap + int(nativeTerrainPercentTruncate(int32(ap), int32(apPct))),
		dp + int(nativeTerrainPercentTruncate(int32(dp), int32(dpPct)))
}

// nativeTerrainPercentTruncate reproduces 0x14237's `imul; sar edx,0x1f;
// idiv 0x64` sequence: signed multiply by percent, divide by 100 truncating
// toward zero (not floor).
func nativeTerrainPercentTruncate(value, percent int32) int32 {
	return int32((int64(value) * int64(percent)) / 100)
}

// NativeAI14237Result is the winning physical-attack candidate 0x14237
// selects, mirroring what it writes to [0x53C43/47/4B/4F].
type NativeAI14237Result struct {
	Destination Cell
	TargetIndex int
	Priority    int
	Score       int
	HasWinner   bool
}

// ScoreNativeAI14237 reproduces FD2.EXE's native physical-attack candidate
// selection (old-doc address 0x14237, new-exe 0x3944b) end to end:
// disassembly-confirmed 2026-08-14 against the live "新版" reference EXE
// (docs/knowledge-base/11-enemy-ai.md's "0x14237 composer" sections have the
// full instruction-level trace this was built from). Composes:
//
//  1. The actor's equipped weapon (0x1B83D-equivalent via
//     NativeEquippedInventorySlot with a2=0; no weapon equipped is not an
//     error -- 0x14237 itself returns "no candidate" in that case) and its
//     item row +0xc (attack range in tiles).
//  2. Reachable destination cells (NativeAIPhysicalDestinations), using the
//     actor's own remaining-movement-budget byte (record+0x3B) as the search
//     budget -- confirmed from the disassembly to NOT be the fixed budget-28
//     mode-0 movement fallback uses; this is 0x14237's own separate call.
//  3. Per destination cell: terrain-adjusted actor AP/DP
//     (nativeAIAdjustedTerrainWords, gated per unit).
//  4. Per destination cell: the target-index array within Manhattan range of
//     the weapon (NativeAIPhysicalAttackTargets), target code fixed to
//     "opposing group" (1 if selector==0, else 0, matching
//     nativeAIOppositeSelectorGroup's convention).
//  5. Per target: terrain-adjusted target AP/DP at the TARGET's own cell,
//     the 0x1DEBE adjacency gate evaluated against the DESTINATION cell (not
//     the target's cell -- confirmed from the disassembled push order), and
//     the full ScoreNativePhysicalAttackCandidate formula.
//  6. SelectNativePhysicalAttackCandidate's priority-then-score winner.
//
// itemRows is the EXE item-effect-row table (same shape native_ai_item_preselection.go
// and native_ai_1debe_adjacency.go already use). baseFlags/terrainMoveCodes/costRow
// are the same raw grid inputs every other native AI primitive in this
// package requires; missing/malformed native data fails closed (ok=false),
// never a partial/guessed result.
func ScoreNativeAI14237(
	w, h int,
	records []byte,
	count, actor, selector int,
	itemRows []byte,
	baseFlags, terrainMoveCodes, costRow []byte,
) (NativeAI14237Result, error) {
	var zero NativeAI14237Result
	if count < 0 || count > 0x100 || len(records) != count*nativeRecordSize ||
		actor < 0 || actor >= count || (selector != 0 && selector != 1) {
		return zero, fmt.Errorf("native AI 0x14237 roster/actor is malformed")
	}
	actorRecord := records[actor*nativeRecordSize:]

	flags := make([]int, nativeInventoryCells)
	slots := make([]int, nativeInventoryCells)
	for cell := 0; cell < nativeInventoryCells; cell++ {
		flags[cell] = int(actorRecord[nativeInventoryOffset+cell*2])
		slots[cell] = int(actorRecord[nativeInventoryOffset+cell*2+1])
	}
	weaponSlot, err := NativeEquippedInventorySlot(flags, slots, 0)
	if err != nil {
		return zero, err
	}
	if weaponSlot < 0 {
		return zero, nil
	}
	itemID := slots[weaponSlot]
	rowOffset, err := NativeItemEffectRowOffset(itemID)
	if err != nil {
		return zero, err
	}
	if rowOffset+0x0d > len(itemRows) {
		return zero, fmt.Errorf("native AI 0x14237 item %d row is unavailable", itemID)
	}
	rangeTiles := int(itemRows[rowOffset+0x0c])

	actorAPRaw := int(binary.LittleEndian.Uint16(actorRecord[0x48:0x4a]))
	actorDPRaw := int(binary.LittleEndian.Uint16(actorRecord[0x4a:0x4c]))
	budget := int(actorRecord[0x3b])

	destinations, err := NativeAIPhysicalDestinations(w, h, records, count, actor, selector, budget, baseFlags, terrainMoveCodes, costRow)
	if err != nil {
		return zero, err
	}

	targetCode := 0
	if selector == 0 {
		targetCode = 1
	}

	candidates := make([]NativePhysicalAttackCandidate, 0)
	for _, dest := range destinations {
		adjustedActorAP, adjustedActorDP := nativeAIAdjustedTerrainWords(
			actorRecord, w, h, terrainMoveCodes, dest.X, dest.Y, actorAPRaw, actorDPRaw,
		)
		targets, err := NativeAIPhysicalAttackTargets(w, h, records, count, dest.X, dest.Y, rangeTiles, targetCode)
		if err != nil {
			return zero, err
		}
		if len(targets) == 0 {
			continue
		}
		debe, err := NativeAI1DEBEAdjacencyGate(records, itemRows, count, actor, dest.X, dest.Y)
		if err != nil {
			return zero, err
		}
		rawHelper := 0
		if debe {
			rawHelper = 1
		}
		for _, targetIndex := range targets {
			targetRecord := records[int(targetIndex)*nativeRecordSize:]
			targetAPRaw := int(binary.LittleEndian.Uint16(targetRecord[0x48:0x4a]))
			targetDPRaw := int(binary.LittleEndian.Uint16(targetRecord[0x4a:0x4c]))
			targetX, targetY := int(targetRecord[0]), int(targetRecord[1])
			adjustedTargetAP, adjustedTargetDP := nativeAIAdjustedTerrainWords(
				targetRecord, w, h, terrainMoveCodes, targetX, targetY, targetAPRaw, targetDPRaw,
			)
			targetHP := int(binary.LittleEndian.Uint16(targetRecord[0x40:0x42]))
			candidates = append(candidates, NativePhysicalAttackCandidate{
				DestinationX: dest.X,
				DestinationY: dest.Y,
				TargetIndex:  int(targetIndex),
				Inputs: NativePhysicalAttackScoreInput{
					ActorWord48:          adjustedActorAP,
					ActorWord4A:          adjustedActorDP,
					TargetWord48:         adjustedTargetAP,
					TargetWord4A:         adjustedTargetDP,
					TargetWord40:         targetHP,
					RawTargetByte8:       targetRecord[8],
					RawHelper1DEBEResult: rawHelper,
				},
			})
		}
	}

	selection, found, err := SelectNativePhysicalAttackCandidate(candidates)
	if err != nil {
		return zero, err
	}
	if !found {
		return zero, nil
	}
	return NativeAI14237Result{
		Destination: Cell{X: selection.Candidate.DestinationX, Y: selection.Candidate.DestinationY},
		TargetIndex: selection.Candidate.TargetIndex,
		Priority:    selection.Ranking.Priority,
		Score:       selection.Ranking.Score,
		HasWinner:   true,
	}, nil
}
