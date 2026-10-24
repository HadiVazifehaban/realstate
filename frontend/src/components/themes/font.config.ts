import localFont from 'next/font/local';
import { cn } from '@/lib/utils';

// Bundle the two scripts the product needs locally. Google-hosted fonts made
// production builds depend on outbound network access and failed in isolated
// Docker builds. Noto Sans Arabic covers Persian; Noto Sans covers Latin.
const fontArabic = localFont({
  src: '../../../public/fonts/NotoSansArabic-Regular.ttf',
  variable: '--font-vazir',
  display: 'swap'
});

const fontLatin = localFont({
  src: [
    { path: '../../../public/fonts/NotoSans-Regular.ttf', weight: '400', style: 'normal' },
    { path: '../../../public/fonts/NotoSans-Bold.ttf', weight: '700', style: 'normal' }
  ],
  variable: '--font-latin-sans',
  display: 'swap'
});

export const fontVariables = cn(fontArabic.variable, fontLatin.variable);
