import type { InfobarContent } from '@/components/ui/infobar';

/** راهنمای این صفحه. */
export const requestsInfoContent: InfobarContent = {
  title: 'درخواست\u200cهای همکاری',
  sections: [
    {
      title: 'دریافتی و ارسالی',
      description:
        'درخواست\u200cهایی که دیگران برای شما فرستاده\u200cاند و درخواست\u200cهایی که شما ارسال کرده\u200cاید را دنبال کنید.'
    },
    {
      title: 'تأیید یا رد',
      description:
        'درخواست دریافتی را تأیید یا رد کنید؛ در صورت تأیید، دو دفتر می\u200cتوانند فایل را به اشتراک بگذارند.'
    }
  ]
};
