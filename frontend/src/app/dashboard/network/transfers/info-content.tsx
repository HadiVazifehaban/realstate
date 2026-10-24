import type { InfobarContent } from '@/components/ui/infobar';

/** راهنمای این صفحه. */
export const transfersInfoContent: InfobarContent = {
  title: 'انتقال فایل\u200cها',
  sections: [
    {
      title: 'انتقال مسئولیت',
      description:
        'انتقال فایل به دفتر دیگر با تأیید صریح انجام می\u200cشود و تاریخچهٔ آن برای همیشه حفظ می\u200cشود.'
    },
    {
      title: 'کارمزد باقی\u200cمانده',
      description:
        'در انتقال می\u200cتوان درصدی از کارمزد برای دفتر قبل باقی گذاشت.'
    }
  ]
};
