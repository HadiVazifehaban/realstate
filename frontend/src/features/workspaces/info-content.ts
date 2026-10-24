import type { InfobarContent } from '@/components/ui/infobar';

/**
 * What the office page is, in the terms the desk uses.
 *
 * Written for this node rather than for the starter template's workspace
 * switcher: a single-office installation has no second workspace to switch to,
 * so the page answers "which office is this and what may I do here" instead.
 */
export const officeInfoContent: InfobarContent = {
  title: 'دفتر من',
  sections: [
    {
      title: 'دفتر و پروانه',
      description:
        'این نود به یک دفتر خدمت می‌کند و هویت آن از پروانهٔ تجاری خوانده می‌شود: نام دفتر، شناسهٔ پروانه، تعداد نشست‌های هم‌زمان و مهلت دورهٔ تنفس آفلاین. وضعیت‌های «قابل استفاده» فقط شامل پروانهٔ فعال و دورهٔ تنفس است؛ بقیهٔ حالت‌ها یعنی نود باید تمدید شود.',
      links: []
    },
    {
      title: 'دورهٔ تنفس آفلاین',
      description:
        'دفتر آفلاین کار می‌کند: نود تا پایان مهلت، بدون تماس با سرور پروانه همهٔ امکانات را دارد. اگر نود تا آن تاریخ با سرور پروانه همگام نشود، وضعیت به «مهلت آفلاین تمام شده» تغییر می‌کند.',
      links: []
    },
    {
      title: 'دسترسی من',
      description:
        'نقش، وضعیت احراز هویت، شناسهٔ دفتر (مستأجر) و سهمیهٔ روزانهٔ مشاهدهٔ اطلاعات مالک از توکن ورود خوانده می‌شوند. این‌ها فقط برای نمایش هستند؛ محدودیت واقعی روی نود و از روی امضاهای همان توکن اعمال می‌شود.',
      links: []
    },
    {
      title: 'تیم دفتر',
      description:
        'توزیع نقش‌ها از دفترچهٔ کاربران نود می‌آید و همان منبعی است که صفحهٔ «کاربران و نقش‌ها» استفاده می‌کند، پس شمارش‌ها هیچ‌وقت با فهرست اختلاف پیدا نمی‌کنند. افزودن، ویرایش و غیرفعال‌سازی کاربر از همان صفحه انجام می‌شود.',
      links: []
    }
  ]
};
