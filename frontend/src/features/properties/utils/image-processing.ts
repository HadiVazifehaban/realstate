/**
 * Client-side image processing helpers for property media.
 *
 * Every helper here is deliberately browser-only (`canvas`, `createImageBitmap`)
 * and each one degrades to "leave the file alone" when an API is missing or the
 * encode fails: a compression that throws must never cost a broker their photo.
 */

/** Target long-edge pixels for a listing photo. 1600 is enough for a full-screen viewer. */
const MAX_EDGE_PX = 1600;

/** WebP quality, 0..1. Listing photos look clean at 0.82 and shrink ~70% vs JPEG. */
const WEBP_QUALITY = 0.82;

/** Skip re-encoding when the original is already below this size (bytes). */
const SMALL_FILE_BYTES = 250 * 1024;

export interface CompressResult {
  /** The file to upload — the compressed one, or the original when skipped. */
  file: File;
  /** True when the uploaded file is the WebP re-encode, not the original. */
  compressed: boolean;
  /** Bytes saved by the re-encode, 0 when skipped. */
  savedBytes: number;
}

/** True when the runtime can run a canvas encode at all. */
function canUseCanvas(): boolean {
  return (
    typeof document !== 'undefined' &&
    typeof document.createElement === 'function' &&
    typeof HTMLCanvasElement !== 'undefined' &&
    typeof HTMLCanvasElement.prototype.toBlob === 'function'
  );
}

/** Fit `width`x`height` inside a `MAX_EDGE_PX` box, never upscaling. */
function fitWithin(width: number, height: number): { width: number; height: number } {
  const longest = Math.max(width, height);
  if (longest <= MAX_EDGE_PX) return { width, height };
  const scale = MAX_EDGE_PX / longest;
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/**
 * Re-encode an image file into WebP, capped at :ref:`MAX_EDGE_PX` on the long edge.
 *
 * Videos and non-images are returned untouched, as are files already small
 * enough that a re-encode would cost quality for little bandwidth, and any file
 * whose decode fails. The returned `file` is always safe to upload.
 */
export async function compressImageToWebP(file: File): Promise<CompressResult> {
  if (!file.type.startsWith('image/')) {
    return { file, compressed: false, savedBytes: 0 };
  }
  // A GIF may be animated; a canvas export would freeze the first frame.
  if (file.type === 'image/gif') {
    return { file, compressed: false, savedBytes: 0 };
  }
  if (!canUseCanvas() || typeof createImageBitmap !== 'function') {
    return { file, compressed: false, savedBytes: 0 };
  }
  if (file.size <= SMALL_FILE_BYTES) {
    return { file, compressed: false, savedBytes: 0 };
  }

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return { file, compressed: false, savedBytes: 0 };
  }

  const { width, height } = fitWithin(bitmap.width, bitmap.height);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    bitmap.close?.();
    return { file, compressed: false, savedBytes: 0 };
  }
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close?.();

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/webp', WEBP_QUALITY);
  });
  // A null blob means the encode did not happen; keep the original bytes.
  if (!blob) {
    return { file, compressed: false, savedBytes: 0 };
  }
  // Never let a "compressed" file be bigger than the source.
  if (blob.size >= file.size) {
    return { file, compressed: false, savedBytes: 0 };
  }

  const name = file.name.replace(/\.[^.]+$/, '') || 'photo';
  const compressedFile = new File([blob], `${name}.webp`, { type: 'image/webp' });
  return {
    file: compressedFile,
    compressed: true,
    savedBytes: file.size - blob.size
  };
}

/**
 * Draw a semi-transparent diagonal watermark across a canvas, returning its blob.
 *
 * Used on preview only — the stamp exists so a screenshot of the preview cannot
 * be reposted as an original listing photo. Returns `null` when canvas encoding
 * is unavailable so the caller can fall back to the plain preview.
 */
export async function drawWatermarkBlob(file: File, label: string): Promise<Blob | null> {
  if (!canUseCanvas() || typeof createImageBitmap !== 'function') return null;
  if (!file.type.startsWith('image/') || file.type === 'image/gif') return null;

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return null;
  }

  const canvas = document.createElement('canvas');
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    bitmap.close?.();
    return null;
  }
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close?.();

  ctx.save();
  ctx.rotate((-Math.PI / 180) * 24);
  const shortest = Math.min(canvas.width, canvas.height);
  const fontSize = Math.max(14, Math.round(shortest / 11));
  ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = 'rgba(255, 255, 255, 0.72)';
  ctx.strokeStyle = 'rgba(0, 0, 0, 0.28)';
  ctx.lineWidth = Math.max(1, fontSize / 12);

  const stepY = fontSize * 3.2;
  // Cover the rotated diagonal, not just the axis-aligned box, or the corners
  // of a landscape photo come out unmarked.
  const span = Math.round(canvas.width + canvas.height);
  for (let y = -span; y < span; y += stepY) {
    for (let x = -span; x < span; x += span * 0.5) {
      ctx.strokeText(label, x + span / 4, y);
      ctx.fillText(label, x + span / 4, y);
    }
  }
  ctx.restore();

  return await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/webp', Math.min(WEBP_QUALITY, 0.9));
  });
}
