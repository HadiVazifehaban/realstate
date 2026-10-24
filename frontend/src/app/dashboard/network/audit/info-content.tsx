import type { InfobarContent } from '@/components/ui/infobar';

/** راهنمای این صفحه. */
export const auditInfoContent: InfobarContent = {
  title: 'رهگیری و لاگ',
  sections: [
    {
      title: 'لاگ امنیتی',
      description:
        'همهٔ رویدادهای حساس شبکه — افشا، خروجی، تغییر دسترسی، لغو، انتقال، تغییر کمیسیون، پرداخت و اختلاف — اینجا ثبت می\u200cشوند.'
    },
    {
      title: 'فیلتر',
      description:
        'لاگ را بر اساس دفتر، کاربر، عملیات، فایل یا بازهٔ زمانی فیلتر کنید.'
    }
  ]
};
