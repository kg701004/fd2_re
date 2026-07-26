package fdother

import (
	"encoding/binary"
	"errors"
)

// DecodeLMI1FrameResource reads one LMI1 directory entry whose native caller
// sends it to 0x4e63d.  LMI1 is a directory, not a universal pixel codec:
// this path deliberately remains separate from ParseLMI1's 0x4e916 cells.
func DecodeLMI1FrameResource(datPath string, resource, index int) (Frame, error) {
	data, err := ReadResource(datPath, resource)
	if err != nil {
		return Frame{}, err
	}
	return ParseLMI1FrameEntry(data, index)
}

// ParseLMI1FrameEntry extracts a single LMI1 entry with a width/height header
// followed by the four-mode RLE consumed by 0x4e63d.  It does not infer that
// neighbouring entries use the same codec.
func ParseLMI1FrameEntry(data []byte, index int) (Frame, error) {
	if len(data) < 6 || string(data[:4]) != "LMI1" {
		return Frame{}, errors.New("fdother: missing LMI1 magic")
	}
	count := int(binary.LittleEndian.Uint16(data[4:]))
	tableEnd := 6 + count*4
	if count == 0 || tableEnd > len(data) || index < 0 || index >= count {
		return Frame{}, errors.New("fdother: LMI1 frame index is invalid")
	}
	off := int(binary.LittleEndian.Uint32(data[6+index*4:]))
	if off < tableEnd || off+4 > len(data) {
		return Frame{}, errors.New("fdother: LMI1 frame offset is invalid")
	}
	return ParseSingleFrame(data[off:])
}
