package battle

import "fmt"

// NativeAIScoredCommandCandidateGroup is one 0x1598a destination followed by
// the record indices emitted by its 0x14818 call. Groups retain 0x14b16's
// row-major destination order and the runtime roster's target order.
type NativeAIScoredCommandCandidateGroup struct {
	Destination   Cell
	TargetIndices []byte
}

// NativeAIScoredCommandCandidateGroups preserves 0x1598a's geometry pipeline:
// command record +3 -> 0x4e040 -> 0x14b16, then command record +4 -> 0x14818.
// Unlike 0x14237's physical path, this caller does not invoke 0x145cd/0x146d1
// to derive occupancy flags from the roster; baseFlags must therefore be the
// exact caller-owned grid snapshot.
func NativeAIScoredCommandCandidateGroups(
	w, h int,
	records []byte,
	count, actor, selector int,
	command NativeCommandRecord,
	baseFlags, terrainMoveCodes, costRow []byte,
) ([]NativeAIScoredCommandCandidateGroup, error) {
	destinations, err := nativeAIScoredCommandDestinations(
		w, h, records, count, actor, command.SelectionMode,
		baseFlags, terrainMoveCodes, costRow,
	)
	if err != nil {
		return nil, err
	}
	targetCode, err := nativeAIScoredCommandTargetCode(command.TargetCode, selector)
	if err != nil {
		return nil, err
	}
	groups := make([]NativeAIScoredCommandCandidateGroup, 0, len(destinations))
	for _, destination := range destinations {
		targets, err := nativeAIScoredCommandTargetIndices(
			w, h, records, count, destination,
			command.EffectMode, targetCode, baseFlags,
		)
		if err != nil {
			return nil, err
		}
		if len(targets) == 0 {
			continue
		}
		groups = append(groups, NativeAIScoredCommandCandidateGroup{
			Destination: destination, TargetIndices: targets,
		})
	}
	return groups, nil
}

func nativeAIScoredCommandDestinations(
	w, h int,
	records []byte,
	count, actor, initialBudget int,
	baseFlags, terrainMoveCodes, costRow []byte,
) ([]Cell, error) {
	if w <= 0 || h <= 0 || len(baseFlags) != w*h || len(terrainMoveCodes) != w*h {
		return nil, fmt.Errorf("native AI scored destination grid is malformed")
	}
	if count < 0 || count > 0x100 || len(records) != count*nativeRecordSize ||
		actor < 0 || actor >= count {
		return nil, fmt.Errorf("native AI scored destination roster/actor is malformed")
	}
	if initialBudget < 0 || initialBudget > 0xff || len(costRow) != NativeMovementCostRowSize {
		return nil, fmt.Errorf("native AI scored destination movement inputs are malformed")
	}
	for cell, code := range terrainMoveCodes {
		if int(code) >= len(costRow) {
			return nil, fmt.Errorf(
				"native AI scored destination terrain code %d at cell %d is out of bounds",
				code, cell,
			)
		}
	}
	actorRecord := records[actor*nativeRecordSize:]
	origin := Cell{X: int(actorRecord[0]), Y: int(actorRecord[1])}
	if origin.X < 0 || origin.Y < 0 || origin.X >= w || origin.Y >= h {
		return nil, fmt.Errorf("native AI scored destination actor is outside the grid")
	}
	field := make([]byte, w*h)
	for index := range field {
		field[index] = 0xff
	}
	field[origin.Y*w+origin.X] = byte(initialBudget)
	nativeAIPropagateDestinationBudget(
		w, h, origin, byte(initialBudget),
		baseFlags, terrainMoveCodes, costRow, field,
	)
	result := make([]Cell, 0)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			if field[y*w+x] != 0xff {
				result = append(result, Cell{X: x, Y: y})
			}
		}
	}
	return result, nil
}

func nativeAIScoredCommandTargetCode(commandTargetCode, selector int) (int, error) {
	if commandTargetCode < 0 || commandTargetCode > 0xff ||
		(selector != 0 && selector != 1) {
		return 0, fmt.Errorf("native AI scored target selector is malformed")
	}
	if selector != 0 {
		return commandTargetCode, nil
	}
	if commandTargetCode == 0 {
		return 1, nil
	}
	return 0, nil
}

func nativeAIScoredCommandTargetIndices(
	w, h int,
	records []byte,
	count int,
	origin Cell,
	effectMode, targetCode int,
	baseFlags []byte,
) ([]byte, error) {
	if count < 0 || count > 0x100 || len(records) != count*nativeRecordSize {
		return nil, fmt.Errorf("native AI scored target roster is malformed")
	}
	cells, err := NativeCommandTargetCells(w, h, origin, effectMode, baseFlags)
	if err != nil {
		return nil, err
	}
	result := make([]byte, 0)
	for index := 0; index < count; index++ {
		record := records[index*nativeRecordSize:]
		if record[5]&1 != 0 || !nativeAIScoredRawTargetMatches(targetCode, record[6]) {
			continue
		}
		cell := Cell{X: int(record[0]), Y: int(record[1])}
		if cells[cell] {
			result = append(result, byte(index))
		}
	}
	return result, nil
}

func nativeAIScoredRawTargetMatches(targetCode int, recordByte6 byte) bool {
	switch targetCode {
	case 0:
		return recordByte6 == 0
	case 1:
		return recordByte6 != 0
	case 2:
		return recordByte6 == 1
	case 3:
		return recordByte6 == 2
	default:
		return false
	}
}
