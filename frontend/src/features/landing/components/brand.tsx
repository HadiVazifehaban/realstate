import Image from "next/image";
import Link from "next/link";
import { BRAND_ASSET_VERSION } from "@/lib/brand";

export function LandingBrand({
  dashboard = false,
  header = false
}: {
  dashboard?: boolean;
  header?: boolean;
}) {
  return (
    <Link
      href={dashboard ? "/dashboard" : "/"}
      className="landing-brand"
      aria-label="شکارچی — صفحهٔ اصلی"
    >
      <span className={header ? "dashboard-brand-mark" : undefined}>
        <Image
          src={`/brand/logo-dark.png?v=${BRAND_ASSET_VERSION}`}
          alt=""
          width={header ? 134 : 48}
          height={header ? 134 : 48}
          unoptimized
        />
      </span>
      {!header && (
        <span>
          <strong>شکارچی</strong>
          <small lang="en" dir="ltr">
            SHEKARCHI
          </small>
        </span>
      )}
    </Link>
  );
}
