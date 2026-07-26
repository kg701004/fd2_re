package fdicon

import "errors"

// CopyNativeIndexedRegion reproduces 0x11eb0's row-by-row memmove contract.
// The caller supplies already-offset indexed buffers and explicit strides;
// the normal map redraw uses source buffer+0x8088, stride 456, width 320,
// height 192, and destination VGA+0x504, stride 320. This primitive neither
// owns a VGA buffer nor presents pixels.
func CopyNativeIndexedRegion(dst []byte, dstStride int, src []byte, srcStride, width, height int) error {
	if dstStride < 0 || srcStride < 0 || width < 0 || height < 0 || dstStride < width || srcStride < width {
		return errors.New("fdicon: invalid native indexed copy region")
	}
	if height == 0 {
		return nil
	}
	last := (height-1)*dstStride + width
	if last > len(dst) || (height-1)*srcStride+width > len(src) {
		return errors.New("fdicon: native indexed copy region exceeds buffer")
	}
	for row := 0; row < height; row++ {
		copy(dst[row*dstStride:row*dstStride+width], src[row*srcStride:row*srcStride+width])
	}
	return nil
}
