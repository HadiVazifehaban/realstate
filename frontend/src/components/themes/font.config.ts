import localFont from 'next/font/local';
import { cn } from '@/lib/utils';

// Bundle fonts locally so production builds and offline deployments do not
// depend on a third-party font host. Vazirmatn's variable webfont covers Persian,
// Arabic, and Latin glyphs across weights 100–900.
const fontArabic = localFont({
  src: '../../../public/fonts/Vazirmatn[wght].woff2',
  variable: '--font-vazir',
  display: 'swap',
  weight: '100 900'
});

export const fontVariables = cn(fontArabic.variable);
