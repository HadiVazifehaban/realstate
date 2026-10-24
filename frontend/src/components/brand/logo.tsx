import Image from 'next/image';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { BRAND_ASSET_VERSION } from '@/lib/brand';

/**
 * Brand mark for the سامانه (Maskanchi) office CRM.
 *
 * Shows appropriate logo based on theme: light/dark variants.
 */
const LOGO_LIGHT_SRC = `/brand/logo-light.png?v=${BRAND_ASSET_VERSION}`;
const LOGO_DARK_SRC = `/brand/logo-dark.png?v=${BRAND_ASSET_VERSION}`;
const LOGO_FALLBACK_SRC = `/brand/logo.png?v=${BRAND_ASSET_VERSION}`;

export function Logo({
  size = 32,
  className,
  priority = false,
  alt = 'لوگوی سامانه شکارچی'
}: {
  /** Square box in px. */
  size?: number;
  className?: string;
  priority?: boolean;
  alt?: string;
}) {
  const { resolvedTheme } = useTheme();
  const logoSrc = resolvedTheme === 'dark' ? LOGO_DARK_SRC : resolvedTheme === 'light' ? LOGO_LIGHT_SRC : LOGO_FALLBACK_SRC;

  return (
    <span
      className={cn('relative inline-block shrink-0 rounded-lg overflow-hidden', className)}
      style={{ width: `var(--logo-size, ${size}px)`, height: `var(--logo-size, ${size}px)` }}
      aria-hidden="true"
    >
      <Image
        src={logoSrc}
        alt={alt}
        fill
        priority={priority}
        unoptimized
        className='object-cover'
        sizes={`${size}px`}
        style={{ borderRadius: 'inherit' }}
      />
    </span>
  );
}
