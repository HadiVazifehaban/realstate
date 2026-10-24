import Link from 'next/link';

export const metadata = { title: 'دسترسی مجاز نیست' };

export default function AccessDeniedPage() {
  return (
    <main dir='rtl' className='flex min-h-svh items-center justify-center p-6'>
      <section className='bg-card text-card-foreground w-full max-w-lg space-y-5 rounded-xl border p-8 text-center'>
        <h1 className='text-2xl font-bold'>حساب شما به این بخش دسترسی ندارد</h1>
        <p className='text-muted-foreground leading-8'>
          ورود شما انجام شده است، اما نقش حساب برای نمایش این بخش مجاز نیست.
          برای بررسی نقش و تأیید حساب، با مدیر سامانه تماس بگیرید.
        </p>
        <Link href='/dashboard/profile' className='text-primary inline-block underline underline-offset-4'>
          مشاهدهٔ حساب کاربری
        </Link>
      </section>
    </main>
  );
}