package fdother

import (
	"encoding/binary"
	"errors"
)

// NativePreparationCommand preserves the exact three-byte record consumed by
// 0x1ac62: one kind byte followed by one little-endian word payload.
type NativePreparationCommand struct {
	Kind    byte
	Payload uint16
}

// ParseNativePreparationCommands decodes count records using native's
// base+3*i addressing. Unknown kind values remain data; callers decide if and
// when a verified branch can execute.
func ParseNativePreparationCommands(raw []byte, count int) ([]NativePreparationCommand, error) {
	if count < 0 || len(raw) < count*3 {
		return nil, errors.New("fdother: preparation command stream is truncated")
	}
	commands := make([]NativePreparationCommand, count)
	for i := range commands {
		offset := i * 3
		commands[i] = NativePreparationCommand{
			Kind: raw[offset], Payload: binary.LittleEndian.Uint16(raw[offset+1:]),
		}
	}
	return commands, nil
}
