'use client';

import * as React from 'react';

import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn, formatBytes, toPersianDigits } from '@/lib/utils';
import { compressImageToWebP, drawWatermarkBlob } from '../utils/image-processing';

/**
 * Media picker for the submit form: photos and a walkthrough video.
 *
 * Files are held in component state until the listing itself exists, then the
 * whole batch goes up in one request (the node's route takes a multipart body,
 * so a batch of 12 is one round trip rather than twelve). Previews are local
 * `blob:` URLs -- the bytes never leave the browser before the advisor commits
 * the form, and they are revoked when a file is dropped or the form resets.
 *
 * Videos get their own row in the UI because they behave differently: a phone
 * walkthrough is 80 MB where a photo is 4, so the ceiling and the expectation
 * both differ. Nothing here transcodes or renames anything -- except images,
 * which are re-encoded to WebP before they take up form state: a 4 MP phone
 * photo is 5-8 MB and the uplink on an office line is the slow leg of the
 * submit. The re-encode is capped at 1600 px on the long edge and skipped
 * outright for small files, so a crisp exterior shot never gets softer than a
 * full-screen viewer can show.
 *
 * Previews carry a diagonal watermark over them. The bytes uploaded are the
 * compressed photo; the watermark exists only so a screenshot of the preview
 * cannot be posted elsewhere as an original listing photo.
 */

interface PropertyMediaUploaderProps {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
  /** Upload progress in percent, owned by the page while a submit is in flight. */
  progress?: number | null;
  className?: string;
}

/** Accepted input types, mirrors of the backend's classify() table. */
const ACCEPT = 'image/jpeg,image/png,image/webp,image/gif,image/avif,video/mp4,video/quicktime,video/webm';

/** Guard rails that mirror the node, so the advisor is told before the upload. */
const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
const MAX_VIDEO_BYTES = 200 * 1024 * 1024;
const MAX_FILES = 20;

/** Diagonal stamp drawn across every photo preview. */
const WATERMARK_LABEL = 'کد آگهی ندارد';

function kindOf(file: File): 'image' | 'video' | 'other' {
  if (file.type.startsWith('image/')) return 'image';
  if (file.type.startsWith('video/')) return 'video';
  return 'other';
}

function ceilingFor(file: File): number {
  return kindOf(file) === 'video' ? MAX_VIDEO_BYTES : MAX_IMAGE_BYTES;
}

export function PropertyMediaUploader({
  files,
  onChange,
  disabled = false,
  progress = null,
  className
}: PropertyMediaUploaderProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  // Object URLs for the chosen files, revoked on unmount or when a file leaves
  // the list -- a leaked blob keeps the page's memory (and the file handle)
  // alive for as long as the tab is open.
  const [previews, setPreviews] = React.useState<Record<string, string>>({});
  // Total bytes the WebP re-encode has saved, so the trade is visible rather
  // than silent.
  const [savedBytes, setSavedBytes] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    const next: Record<string, string> = {};

    void (async () => {
      for (const file of files) {
        if (kindOf(file) !== 'image') continue;
        // Watermarked preview, falling back to the raw file when canvas is
        // unavailable -- the preview is cosmetic, so it never blocks the pick.
        const blob = await drawWatermarkBlob(file, WATERMARK_LABEL);
        if (cancelled) return;
        const url = blob
          ? URL.createObjectURL(new File([blob], file.name, { type: blob.type }))
          : URL.createObjectURL(file);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        next[file.name + file.size] = url;
      }
      if (cancelled) return;
      setPreviews((prev) => {
        for (const key of Object.keys(prev)) {
          if (!(key in next)) URL.revokeObjectURL(prev[key]);
        }
        return next;
      });
    })();

    return () => {
      cancelled = true;
      for (const key of Object.keys(next)) URL.revokeObjectURL(next[key]);
    };
  }, [files]);

  const [dragOver, setDragOver] = React.useState(false);
  const [rejected, setRejected] = React.useState<string | null>(null);

  const add = React.useCallback(
    async (incoming: FileList | null) => {
      if (!incoming) return;
      const accepted: File[] = [];
      const problems: string[] = [];
      for (const file of Array.from(incoming)) {
        if (files.length + accepted.length >= MAX_FILES) {
          problems.push(`حداکثر ${toPersianDigits(MAX_FILES.toLocaleString('en-US'))} فایل.`);
          break;
        }
        if (kindOf(file) === 'other') {
          problems.push(`${file.name}: فرمت پشتیبانی نمی‌شود.`);
          continue;
        }
        if (file.size > ceilingFor(file)) {
          problems.push(`${file.name}: بزرگ‌تر از حد مجاز.`);
          continue;
        }
        if (files.some((f) => f.name === file.name && f.size === file.size)) continue;
        accepted.push(file);
      }

      // Image re-encode happens after the cheap checks so a rejected file never
      // pays the decode cost. Sequential rather than Promise.all: ten 8 MP
      // photos decoded at once would spike memory on a low-end office machine.
      let saved = 0;
      for (let index = 0; index < accepted.length; index += 1) {
        try {
          const result = await compressImageToWebP(accepted[index]);
          saved += result.savedBytes;
          accepted[index] = result.file;
        } catch {
          // A failed re-encode leaves the original in place; a photo the
          // advisor chose is better than one the tool optimised away.
        }
      }

      setSavedBytes((total) => total + saved);
      if (accepted.length) onChange([...files, ...accepted]);
      setRejected(problems.length ? problems.join(' ') : null);
    },
    [files, onChange]
  );

  const remove = (index: number) => {
    onChange(files.filter((_, i) => i !== index));
    setRejected(null);
  };

  /** First image is the cover, matching the node's own "first photo wins" rule. */
  const coverIndex = files.findIndex((file) => kindOf(file) === 'image');

  return (
    <div className={cn('space-y-3', className)}>
      <input
        ref={inputRef}
        type='file'
        accept={ACCEPT}
        multiple
        hidden
        disabled={disabled}
        onChange={(event) => {
          const picked = event.target.files;
          // Reset first so the same file can be picked twice; the async add
          // then reads the detached FileList (still valid after reset).
          event.target.value = '';
          void add(picked);
        }}
      />

      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          if (!disabled) void add(event.dataTransfer.files);
        }}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors',
          dragOver ? 'border-gold-accent bg-gold-accent/10' : 'border-border',
          disabled && 'pointer-events-none opacity-60'
        )}
      >
        <span className='bg-gold-accent/10 text-gold-accent flex size-11 items-center justify-center rounded-full'>
          <Icons.media className='size-5' aria-hidden />
        </span>
        <p className='text-sm font-medium'>عکس یا ویدیو ملک را اینجا رها کنید</p>
        <p className='text-muted-foreground text-xs'>
          JPEG، PNG، WebP، GIF یا AVIF — ویدیوی MP4/MOV/WebM تا ۲۰۰ مگابایت؛ عکس‌ها به‌صورت WebP فشرده می‌شوند.
        </p>
        <Button
          type='button'
          variant='outline'
          size='sm'
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          className='mt-1'
        >
          <Icons.upload className='size-3.5' aria-hidden />
          انتخاب فایل
        </Button>
      </div>

      {rejected && <p className='text-destructive text-xs'>{rejected}</p>}

      {savedBytes > 0 && files.length > 0 && (
        <p className='text-muted-foreground flex items-center gap-1.5 text-xs'>
          <Icons.check className='size-3.5 shrink-0' aria-hidden />
          {toPersianDigits((savedBytes / 1024 / 1024).toFixed(1))} مگابایت از حجم عکس‌ها کم شد (فشرده‌سازی WebP).
        </p>
      )}

      {progress !== null && (
        <div className='space-y-1'>
          <Progress value={progress} className='h-1.5' />
          <p className='text-muted-foreground text-xs tabular-nums'>
            {toPersianDigits(Math.round(progress).toLocaleString('en-US'))}٪ آپلود شد
          </p>
        </div>
      )}

      {files.length > 0 && (
        <ul className='grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5'>
          {files.map((file, index) => {
            const key = file.name + file.size;
            const kind = kindOf(file);
            const preview = previews[key];
            return (
              <li
                key={key}
                className='group/item border-border bg-muted/40 relative aspect-4/3 overflow-hidden rounded-lg border'
              >
                {kind === 'image' && preview ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={preview} alt={file.name} className='size-full object-cover' />
                ) : (
                  <div className='text-muted-foreground flex size-full flex-col items-center justify-center gap-1 p-2'>
                    <Icons.video className='size-5' aria-hidden />
                    <span className='w-full truncate text-center text-[10px]'>{file.name}</span>
                  </div>
                )}

                {index === coverIndex && (
                  <span className='absolute top-1 end-1 rounded-full bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-[#ffd8be] backdrop-blur-sm'>
                    کاور
                  </span>
                )}

                <button
                  type='button'
                  onClick={() => remove(index)}
                  aria-label={`حذف ${file.name}`}
                  className='absolute inset-x-0 bottom-0 flex items-center justify-center gap-1.5 bg-black/70 py-1 text-[11px] text-white opacity-0 transition-opacity group-hover/item:opacity-100 focus-visible:opacity-100'
                >
                  <Icons.close className='size-3.5' aria-hidden />
                  {formatBytes(file.size)}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default PropertyMediaUploader;
