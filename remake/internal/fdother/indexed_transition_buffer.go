package fdother

import "fmt"

// Native indexed-transition geometry recovered from 0x24618/0x11eb0. The
// staging image is a 456-byte-stride 312x192 viewport at byte offset 32904 in
// the 128K work buffer; presentation copies it to the 320-byte VGA surface.
const (
	NativeTransitionStageOffset   = 32904
	NativeTransitionStageStride   = 456
	NativeTransitionStageWidth    = 312
	NativeTransitionStageHeight   = 192
	NativeTransitionPresentStride = 320
)

// CopyNativeTransitionBuffer is the exact full-buffer seed performed by the
// native memmove before each 0x22046 descriptor pass. It intentionally does
// not decode the descriptor or apply a LUT.
func CopyNativeTransitionBuffer(dst, src []byte) error {
	if len(src) == 0 || len(dst) < len(src) {
		return fmt.Errorf("indexed transition: destination buffer is too small")
	}
	copy(dst[:len(src)], src)
	return nil
}

// CopyNativeTransitionViewport mirrors 0x11eb0(a1=VGA,a2=320,a3=stage,
// a4=456,a5=312,a6=192). It is a raw indexed copy only; palette and descriptor
// semantics remain the caller's responsibility.
func CopyNativeTransitionViewport(dst []byte, dstStride int, src []byte, srcOffset, srcStride, width, height int) error {
	if dstStride <= 0 || srcStride <= 0 || width <= 0 || height <= 0 || width > dstStride || width > srcStride || srcOffset < 0 || srcOffset%srcStride+width > srcStride {
		return fmt.Errorf("indexed transition: invalid viewport geometry")
	}
	if srcOffset+height*srcStride > len(src) || (height-1)*dstStride+width > len(dst) {
		return fmt.Errorf("indexed transition: viewport exceeds buffer")
	}
	for row := 0; row < height; row++ {
		copy(dst[row*dstStride:row*dstStride+width], src[srcOffset+row*srcStride:srcOffset+row*srcStride+width])
	}
	return nil
}
