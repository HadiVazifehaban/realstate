import type { InfobarContent } from '@/components/ui/infobar';

/** راهنمای این صفحه. */
export const commissionsInfoContent: InfobarContent = {
  title: 'کمیسیون و تسویه',
  sections: [
    {
      title: 'توافق و سهم\u200cها',
      description:
        'توافق کمیسیون بین دو دفتر را با درصد یا مبلغ ثابت تعریف کنید و پس از قفل، سهم\u200cها تغییرناپذیر می\u200cشوند.'
    },
    {
      title: 'پرداخت و مانده',
      description:
        'پرداخت\u200cهای هر سهم را ثبت کنید و ماندهٔ باقی\u200cمانده را دنبال کنید.'
    }
  ]
};
