package ending

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
)

// RenderDATOFrameAt executes the opaque 0x4e8af paste only. Native callers
// provide the staging destination (typically staging+[0x53c67]); the helper
// keeps that offset explicit so it cannot silently become a guessed anchor.
func RenderDATOFrameAt(dst []byte, frame dato.Frame, stride, destinationOffset int) error {
	if len(dst) != Bytes {
		return fmt.Errorf("ending: DATO destination must be %d bytes", Bytes)
	}
	if err := frame.BlitAtOffset(dst, stride, destinationOffset); err != nil {
		return fmt.Errorf("ending: DATO frame at %#x: %w", destinationOffset, err)
	}
	return nil
}
