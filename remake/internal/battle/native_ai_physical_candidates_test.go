package battle

import (
	"errors"
	"reflect"
	"testing"
)

func TestBuildNativeAIPhysicalAttackCandidatesKeepsRawGeometryAndOrder(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	// actor: raw +6==0 at (0,0)
	records[0], records[1], records[6] = 0, 0, 0
	// two opposite raw +6==1 targets
	first := nativeRecordSize
	records[first], records[first+1], records[first+6] = 2, 0, 1
	second := 2 * nativeRecordSize
	records[second], records[second+1], records[second+6] = 1, 1, 1
	before := append([]byte(nil), records...)

	terrain := make([]byte, 6)
	cost := make([]byte, NativeMovementCostRowSize)
	for index := range cost {
		cost[index] = 1
	}
	seen := make([]NativeAIPhysicalAttackRawCandidate, 0)
	candidates, err := BuildNativeAIPhysicalAttackCandidates(
		3, 2, records, 3, 0, 0, 2,
		NativeAIPhysicalAttackGeometry{TargetMode: 1, TargetInnerMark: 0, TargetCode: 1},
		make([]byte, 6), make([]byte, 6), terrain, cost,
		func(raw NativeAIPhysicalAttackRawCandidate) (NativePhysicalAttackScoreInput, error) {
			seen = append(seen, raw)
			if len(raw.ActorRecord) != nativeRecordSize || len(raw.TargetRecord) != nativeRecordSize {
				t.Fatalf("raw record lengths=%d/%d", len(raw.ActorRecord), len(raw.TargetRecord))
			}
			if raw.ActorRecord[6] != 0 || raw.TargetRecord[6] != 1 {
				t.Fatalf("raw groups actor=%d target=%d", raw.ActorRecord[6], raw.TargetRecord[6])
			}
			// The resolver is caller-owned terrain/helper provenance. Keep the
			// test values raw-shaped; no Camp/X/Y projection is used.
			if raw.TargetIndex == 2 {
				return NativePhysicalAttackScoreInput{
					ActorWord48: 14, TargetWord4A: 1, TargetWord40: 3,
					RawTargetByte8: 1,
				}, nil
			}
			return NativePhysicalAttackScoreInput{
				ActorWord48: 14, TargetWord4A: 10, TargetWord40: 3,
				RawTargetByte8: 1,
			}, nil
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(records, before) {
		t.Fatal("candidate builder mutated raw records")
	}
	if len(candidates) != 3 || len(seen) != len(candidates) {
		t.Fatalf("candidate count=%d seen=%d, want 3", len(candidates), len(seen))
	}
	if candidates[0].DestinationX != 1 || candidates[0].DestinationY != 0 || candidates[0].TargetIndex != 1 {
		t.Fatalf("first candidate=%+v, want row-major destination (1,0)/target 1", candidates[0])
	}
	selection, ok, err := SelectNativePhysicalAttackCandidate(candidates)
	if err != nil || !ok {
		t.Fatalf("selection ok=%v err=%v", ok, err)
	}
	if selection.Candidate.TargetIndex != 2 || selection.Ranking != (NativePhysicalAttackScore{Priority: 18, Score: 26}) {
		t.Fatalf("selection=%+v, want target 2 priority18 score26", selection)
	}

	// The resolver receives detached snapshots, not aliases into the input.
	seen[0].ActorRecord[0] = 0xff
	if records[0] == 0xff {
		t.Fatal("resolver received aliased actor record")
	}
}

func TestBuildNativeAIPhysicalAttackCandidatesFailsClosedWithoutScoreProvenance(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[6] = 0
	terrain := make([]byte, 1)
	cost := make([]byte, NativeMovementCostRowSize)
	for index := range cost {
		cost[index] = 1
	}
	if _, err := BuildNativeAIPhysicalAttackCandidates(
		1, 1, records, 1, 0, 0, 0,
		NativeAIPhysicalAttackGeometry{TargetMode: 1, TargetCode: 1},
		terrain, terrain, terrain, cost, nil,
	); err == nil {
		t.Fatal("missing raw score resolver was accepted")
	}
}

func TestBuildNativeAIPhysicalAttackCandidatesRejectsResolverError(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[6] = 0
	records[nativeRecordSize+6] = 1
	records[nativeRecordSize], records[nativeRecordSize+1] = 1, 0
	terrain := make([]byte, 2)
	cost := make([]byte, NativeMovementCostRowSize)
	for index := range cost {
		cost[index] = 1
	}
	_, err := BuildNativeAIPhysicalAttackCandidates(
		2, 1, records, 2, 0, 0, 1,
		NativeAIPhysicalAttackGeometry{TargetMode: 1, TargetCode: 1},
		terrain, terrain, terrain, cost,
		func(NativeAIPhysicalAttackRawCandidate) (NativePhysicalAttackScoreInput, error) {
			return NativePhysicalAttackScoreInput{}, errors.New("raw score provenance unavailable")
		},
	)
	if err == nil {
		t.Fatal("resolver error was swallowed")
	}
}
