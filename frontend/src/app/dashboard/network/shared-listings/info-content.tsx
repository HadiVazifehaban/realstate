import type { InfobarContent } from '@/components/ui/infobar';

/** راهنمای این صفحه. */
export const sharedListingsInfoContent: InfobarContent = {
  title: 'فایل\u200cهای اشتراکی',
  sections: [
    {
      title: 'اشتراک ارسالی و دریافتی',
      description:
        'فایل\u200cهایی را که به دفاتر دیگر فرستاده\u200cاید یا از آن\u200cها دریافت کرده\u200cاید ببینید.'
    },
    {
      title: 'لغو و تمدید',
      description:
        'در هر لحظه می\u200cتوانید دسترسی یک اشتراک را لغو کنید یا مهلت آن را تمدید کنید. شمارهٔ مالک و آدرس دقیق پیش\u200cفرض پنهان می\u200cمانند.'
    }
  ]
};
