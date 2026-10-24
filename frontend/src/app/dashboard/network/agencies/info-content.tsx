import type { InfobarContent } from '@/components/ui/infobar';

/** راهنمای این صفحه. */
export const agenciesInfoContent: InfobarContent = {
  title: 'دفاتر همکار',
  sections: [
    {
      title: 'فهرست و جستجو',
      description:
        'همهٔ دفاتر شبکه را بر اساس نام، شهر یا منطقه پیدا کنید و وضعیت اعتماد هر دفتر را ببینید.'
    },
    {
      title: 'درخواست همکاری',
      description:
        'برای شروع همکاری با یک دفتر، «درخواست همکاری» را بزنید. درخواست پس از تأیید طرف مقابل فعال می\u200cشود.'
    }
  ]
};
