package fdother

import (
	"encoding/binary"
	"errors"
	"fmt"
	"os"
)

// ParseLUTBank reads FDOTHER #3's LMI1 directory form: magic, u16 count,
// u32 relative offsets, then 256-byte indexed remap tables. It is intentionally
// separate from ParseLMI1, whose entries are width/height UI sprites.
func ParseLUTBank(data []byte) ([][]byte, error) {
	if len(data) < 6 || string(data[:4]) != "LMI1" {
		return nil, errors.New("fdother: missing LUT-bank LMI1 magic")
	}
	count := int(binary.LittleEndian.Uint16(data[4:]))
	if count == 0 || 6+count*4 > len(data) {
		return nil, errors.New("fdother: invalid LUT-bank directory")
	}
	luts := make([][]byte, count)
	for i := range luts {
		off := int(binary.LittleEndian.Uint32(data[6+i*4:]))
		if off < 6+count*4 || off+256 > len(data) {
			return nil, fmt.Errorf("fdother: LUT %d bounds invalid", i)
		}
		luts[i] = append([]byte(nil), data[off:off+256]...)
	}
	return luts, nil
}

// DecodeLUTResource opens one player-provided FDOTHER archive entry as a
// native 256-entry LUT bank.
func DecodeLUTResource(datPath string, resource int) ([][]byte, error) {
	data, err := os.ReadFile(datPath)
	if err != nil {
		return nil, err
	}
	entry, err := ArchiveEntry(data, resource)
	if err != nil {
		return nil, err
	}
	return ParseLUTBank(entry)
}

// NativeUnitPresentBridgeLUT materializes the deliberately unaligned table
// returned by 0x22547. The helper exits through a shared epilogue which returns
// FDOTHER #3 entry0 pointer+1; 0x22046 still indexes 256 bytes from that
// address. Since native entries are contiguous 0x100-byte tables, byte 255 of
// this view is entry1[0]. It is neither ordinary LUT0 nor LUT1.
func NativeUnitPresentBridgeLUT(luts [][]byte) ([]byte, error) {
	if len(luts) < 2 || len(luts[0]) != 256 || len(luts[1]) != 256 {
		return nil, errors.New("fdother: incomplete unit-present bridge LUT source")
	}
	bridge := make([]byte, 256)
	copy(bridge, luts[0][1:])
	bridge[255] = luts[1][0]
	return bridge, nil
}
