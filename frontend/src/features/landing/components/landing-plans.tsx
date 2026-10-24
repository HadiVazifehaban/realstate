"use client";

import Link from "next/link";
import {
  IconSparkles,
  IconMedal,
  IconAward,
  IconCrown,
  IconCheck,
  IconArrowLeft,
  IconStar,
  IconShieldCheck
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { fetchPlans, toman } from "@/features/billing/api/client";
import { landingRoutes } from "../config";

const presentation: Record<string, { label: string; description: string }> = {
  free: { label: "FREE", description: "شروع آشنایی با امکانات شکارچی" },
  monthly: { label: "BRONZE", description: "اشتراک کوتاه‌مدت برای مجموعهٔ شما" },
  quarterly: { label: "SILVER", description: "اشتراک فصلی برای فعالیت مستمر" },
  yearly: { label: "GOLD", description: "اشتراک بلندمدت با سهمیه‌های کاتالوگ" }
};

export function LandingPlans() {
  const plans = useQuery({ queryKey: ["billing", "plans"], queryFn: fetchPlans });
  return (
    <section
      id="subscription-plans"
      className="landing-container landing-plans"
      aria-labelledby="plans-heading"
    >
      <div className="landing-section-heading">
        <span id="pricing" className="landing-anchor" aria-hidden="true" />
        <p className="landing-kicker">تعرفه و اشتراک آژانس‌ها</p>
        <span className="landing-section-english" lang="en">
          AGENCY SUBSCRIPTION PLANS
        </span>
        <h2 id="plans-heading">اشتراکی متناسب با رشد مجموعهٔ شما</h2>
        <p>قیمت و سهمیه‌ها مستقیماً از کاتالوگ اشتراک سامانه دریافت می‌شوند.</p>
      </div>
      {plans.isPending ? (
        <p role="status" className="landing-data-note">
          در حال دریافت تعرفه‌های معتبر…
        </p>
      ) : plans.isError ? (
        <div role="alert" className="landing-data-note">
          دریافت تعرفه‌ها ممکن نشد. قیمت تأییدنشده نمایش داده نمی‌شود.{" "}
          <button type="button" onClick={() => void plans.refetch()}>
            تلاش دوباره
          </button>{" "}
          یا <Link href={landingRoutes.billing}>مشاهدهٔ صفحهٔ اشتراک</Link>
        </div>
      ) : plans.data?.plans.length ? (
        <div className="landing-plans-grid">
          {plans.data.plans.map((plan) => {
            const PlanIcon =
              plan.id === "yearly"
                ? IconCrown
                : plan.id === "quarterly"
                  ? IconAward
                  : plan.id === "monthly"
                    ? IconMedal
                    : IconSparkles;
            return (
              <article
                className={`landing-plan landing-plan-${plan.id in presentation ? plan.id : "custom"}`}
                key={plan.id}
                aria-labelledby={`plan-${plan.id}-title`}
              >
                <div className="landing-plan-top">
                  <span className="landing-plan-icon">
                    <PlanIcon aria-hidden size={27} stroke={1.5} />
                  </span>
                  <span className="landing-plan-label" dir="ltr" lang="en">
                    {presentation[plan.id]?.label ?? plan.id.toUpperCase()}
                  </span>
                </div>
                {plan.id === "yearly" && (
                  <span className="landing-plan-badge">
                    <IconStar aria-hidden size={14} />
                    اشتراک سالانه
                  </span>
                )}
                <h3 id={`plan-${plan.id}-title`}>{plan.title}</h3>
                <p className="landing-plan-description">
                  {presentation[plan.id]?.description ?? "جزئیات اشتراک مطابق کاتالوگ سامانه"}
                </p>
                <div className="landing-plan-pricing">
                  <div className="landing-plan-price-context" aria-hidden="true" />
                  <p className="landing-plan-price">
                    {plan.price_toman === 0 ? (
                      "رایگان"
                    ) : (
                      <>
                        {toman(plan.price_toman)} <small>تومان</small>
                      </>
                    )}
                  </p>
                  <p className="landing-plan-duration">دورهٔ {toman(plan.duration_days)} روزه</p>
                </div>
                <ul>
                  <li>
                    <span className="landing-plan-check">
                      <IconCheck aria-hidden size={14} />
                    </span>
                    سهمیهٔ آگهی:{" "}
                    {plan.is_unlimited
                      ? "نامحدود طبق سیاست استفادهٔ منصفانه"
                      : plan.listing_quota === null
                        ? "طبق سیاست استفادهٔ منصفانه"
                        : toman(plan.listing_quota)}
                  </li>
                  <li>
                    <span className="landing-plan-check">
                      <IconCheck aria-hidden size={14} />
                    </span>
                    پیامک رادار لید: {toman(plan.sms_quota)}
                  </li>
                  <li>
                    <span className="landing-plan-check">
                      <IconCheck aria-hidden size={14} />
                    </span>
                    سهمیهٔ مناطق رادار: {toman(plan.regions_quota)}
                  </li>
                  <li>
                    <span className="landing-plan-check">
                      <IconCheck aria-hidden size={14} />
                    </span>
                    تعداد مشاور:{" "}
                    {plan.advisor_quota === null
                      ? "طبق سیاست استفادهٔ منصفانه"
                      : toman(plan.advisor_quota)}
                  </li>
                  {plan.features.map((feature, index) => (
                    <li key={`${feature}-${index}`}>
                      <span className="landing-plan-check">
                        <IconCheck aria-hidden size={14} />
                      </span>
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  className="landing-button landing-button-outline"
                  href={landingRoutes.billing}
                >
                  مشاهده و انتخاب {plan.title}
                  <IconArrowLeft aria-hidden size={18} />
                </Link>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="landing-data-note">در حال حاضر پلنی برای نمایش ارائه نشده است.</p>
      )}
      <p className="landing-data-note">
        سهمیهٔ پلن به‌معنای پوشش جغرافیایی همهٔ شهرها یا مناطق نیست. پوشش تحلیل و نقشه به داده‌های موجود
        وابسته است. جزئیات نهایی در صفحهٔ اشتراک نمایش داده می‌شود.
      </p>
      <p className="landing-payment-note">
        <IconShieldCheck aria-hidden size={22} />
        <strong>پرداخت کارت‌به‌کارت با تأیید مالی</strong>
        فرآیند موجود: ایجاد سفارش، پرداخت کارت‌به‌کارت و ارسال رسید در بخش اشتراک؛ فعال‌سازی فقط پس از
        تأیید واحد مالی و مطابق وضعیت سفارش انجام می‌شود. سفارش آزمایشی، اشتراک را فعال نمی‌کند.
        انتخاب لینک‌های این صفحه هیچ سفارش یا پرداختی ایجاد نمی‌کند.
      </p>
    </section>
  );
}
