"use client";

import * as React from "react";
import Link from "next/link";
import { A11y, Autoplay, Navigation, Scrollbar } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";
import { Icons } from "@/components/icons";
import { cn, toPersianDigits } from "@/lib/utils";
import type { PropertySummary } from "../types";
import type { MarketMedians } from "../utils/market";
import { marketMedianFor } from "../utils/market";
import { PropertyCard, type ShowcaseVariant } from "./property-card";
import { AddToLeadsButton } from "./add-to-leads-button";

/**
 * One showcase row: header (glow spine + view-all) over a Swiper carousel.
 *
 * Swiper replaces the hand-rolled scroll container. Both could present the same
 * cards, but only Swiper actually *is* a carousel: it owns the transition, the
 * snap points, the keyboard and ARIA plumbing, and it exposes the current slide
 * for free. The previous version re-implemented all of that by hand — measuring
 * `scrollLeft` on a `scroll` listener and manually flipping a `disabled`
 * attribute — which is exactly the kind of thing a battle-tested library is for.
 *
 * Layout is unchanged: 300px slides, one card visible per slide at `sm` and up,
 * `min(78vw, 300px)` below that.
 */

interface ShowcaseRailProps {
  title: string;
  subtitle: string;
  variant: ShowcaseVariant;
  items: PropertySummary[];
  total: number;
  loading: boolean;
  viewAllHref: string;
  /**
   * Benchmarks for both deal families, keyed by ``city::neighborhood``.
   *
   * A rail is a curated selection of the same book the grid below shows, so its
   * cards are judged against the same markets rather than reading as a
   * different (unmarked) class of listing — including its lease cards, which
   * are compared on deposit rather than price per metre.
   */
  marketMedians?: MarketMedians;
}

const RAIL_LIMIT = 12;

export function ShowcaseRail({
  title,
  subtitle,
  variant,
  items,
  total,
  loading,
  viewAllHref,
  marketMedians
}: ShowcaseRailProps) {
  // The buttons drive the instance directly rather than through Swiper's
  // selector-based Navigation module, so each rail's pills stay bound to its own
  // carousel without any id bookkeeping.
  const swiperRef = React.useRef<import("swiper").Swiper | null>(null);

  // Navigation is `disabled` on the first slide by default, which reads as
  // broken when a rail opens mid-list. Re-derive it from the live instance
  // instead, so the pills stay meaningful at both ends.
  const [atStart, setAtStart] = React.useState(true);
  const [atEnd, setAtEnd] = React.useState(false);

  // Auto-advance pauses on hover/focus and resumes on leave; the pill below
  // lets the advisor freeze the rail explicitly (e.g. while reading a card),
  // which a hover-only pause cannot offer on touch screens.
  const [autoplayOn, setAutoplayOn] = React.useState(true);

  const syncEdges = React.useCallback(() => {
    const swiper = swiperRef.current;
    if (!swiper) return;
    setAtStart(swiper.isBeginning);
    setAtEnd(swiper.isEnd);
  }, []);

  const toggleAutoplay = React.useCallback(() => {
    const swiper = swiperRef.current;
    const next = !autoplayOn;
    setAutoplayOn(next);
    if (!swiper?.autoplay) return;
    // `start()` resumes the delay timer; `stop()` freezes the rail where
    // it is. Neither touches the slide index, so toggling never jumps.
    if (next) swiper.autoplay.start();
    else swiper.autoplay.stop();
  }, [autoplayOn]);

  const visible = items.slice(0, RAIL_LIMIT);

  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="lux-section-title">
            {title}
            {total > 0 && (
              <span className="rounded-full border border-[rgba(229,168,123,0.3)] bg-[rgba(229,168,123,0.08)] px-2.5 py-0.5 text-[11px] font-semibold tabular-nums text-gold-primary">
                {toPersianDigits(total.toLocaleString("en-US"))}
              </span>
            )}
          </h2>
          <p className="mt-1 truncate text-xs text-[#94a3b8]">{subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {/*
           * Rail navigation. These were `hidden sm:flex`, i.e. absent on every
           * phone -- the one place a swipe is least reliable and a tap target is
           * most needed. They are shown at every width now.
           */}
          <div className="flex items-center gap-1.5" role="group" aria-label="پیمایش ریل">
            <button
              type="button"
              onClick={() => swiperRef.current?.slidePrev()}
              disabled={atStart}
              aria-label="قبلی"
              className="lux-nav-pill lux-nav-pill--prev"
            >
              <Icons.chevronRight aria-hidden className="size-4" />
            </button>
            <button
              type="button"
              onClick={toggleAutoplay}
              aria-label={autoplayOn ? 'توقف جابه‌جایی خودکار' : 'شروع جابه‌جایی خودکار'}
              aria-pressed={autoplayOn}
              title={autoplayOn ? 'توقف جابه‌جایی خودکار' : 'شروع جابه‌جایی خودکار'}
              className="lux-nav-pill"
            >
              {autoplayOn ? (
                <Icons.pause aria-hidden className="size-4" />
              ) : (
                <Icons.play aria-hidden className="size-4" />
              )}
            </button>
            <button
              type="button"
              onClick={() => swiperRef.current?.slideNext()}
              disabled={atEnd}
              aria-label="بعدی"
              className="lux-nav-pill lux-nav-pill--next"
            >
              <Icons.chevronLeft aria-hidden className="size-4" />
            </button>
          </div>
          <Link
            href={viewAllHref}
            className="group inline-flex items-center gap-1.5 rounded-full border border-[rgba(229,168,123,0.3)] bg-[rgba(229,168,123,0.06)] px-3.5 py-1.5 text-xs font-semibold text-gold-primary transition-all hover:border-gold-accent hover:shadow-[0_0_16px_rgb(229_168_123/0.35)]"
          >
            مشاهده همه
            <Icons.arrowRight
              aria-hidden
              className="size-3.5 transition-transform group-hover:-translate-x-0.5"
            />
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="-mx-1 flex gap-4 overflow-hidden px-1" aria-hidden>
          {Array.from({ length: 4 }, (_, i) => (
            <div
              key={i}
              className="lux-skeleton h-[380px] basis-[min(78vw,300px)] shrink-0 sm:basis-[300px]"
            />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="flex items-center gap-3 rounded-[18px] border border-dashed border-[rgba(229,168,123,0.25)] bg-[rgba(18,26,38,0.4)] px-4 py-6 text-sm text-[#94a3b8]">
          <Icons.inbox aria-hidden className="size-5 shrink-0 text-gold-accent/70" />
          در این ویترین هنوز ملکی ثبت نشده است.
        </div>
      ) : (
        /*
         * The rail shows six listings at a time. With
         * `slidesPerView="auto"` the visible count is however many 300px cards
         * fit the track -- which grows with the viewport, so a wide monitor
         * showed six. The track is therefore capped at the width six cards
         * actually occupy:
         *
         *   6 cards x 300px + 5 gaps x 16px = 1880px of content
         *
         * The Swiper keeps its own `px-1` (4px per side) for the edge fade, so
         * 1880 + 8 = 1888px on this wrapper. A seventh card would need 2196px of
         * content, so the cap leaves a wide margin above it: six is the
         * ceiling, not a coincidence of the current viewport.
         *
         * On narrower viewports the rail scrolls: the draggable scrollbar
         * advances it by hand, the nav pills step it, and autoplay nudges it
         * every 3.5s (pausing on hover or via the play/pause pill).
         */
        <div className="w-full min-w-0 max-w-[1888px]">
          {/*
            `w-full` + `min-w-0`, NOT `mx-auto` alone. This wrapper is a
            stretched item of the section's flex column, and two sizing rules
            were fighting it:

            1. `mx-auto` turns the auto inline margins into the sizing rule, so
               instead of stretching to the section the wrapper shrink-wraps the
               Swiper's max-content (twelve 300px slides) -- and the
               `max-w-[1888px]` cap then pins it at 1888px on EVERY viewport,
               a 375px phone included. A definite `width: 100%` leaves the auto
               margins nothing to absorb, so the wrapper takes the section's
               width and the cap only bites on an ultrawide monitor where six
               cards still fit.

            2. As a flex item its automatic minimum size is its content's
               min-content (those same twelve slides), and that floor alone
               kept the dashboard page ~1900px wide on every viewport.
               `min-w-0` breaks the floor so the rail scrolls inside its own
               track instead of blowing the page out.

            Together these are what clipped the cards off-screen before.
          */}
          <Swiper
            modules={[Navigation, Scrollbar, Autoplay, A11y]}
            onSwiper={(swiper) => {
              swiperRef.current = swiper;
              syncEdges();
            }}
            onSlideChange={syncEdges}
            onResize={syncEdges}
            // `slidesPerView="auto"` makes Swiper read each slide's own
            // `offsetWidth` instead of deriving widths by dividing the container
            // by a fixed slide count. That division is what produced
            // `style="width: 15918200px"` on every slide -- one card filling the
            // viewport and the other seven shoved millions of pixels off-screen,
            // which is exactly the "only the first card shows, the rest are
            // empty" symptom. With "auto" the slide's own `w-[300px]` is
            // authoritative and the arithmetic cannot run away.
            spaceBetween={16}
            slidesPerView="auto"
            // A nudge, not a race: 3.5s per step at the default 300ms slide
            // speed reads as a calm showcase rotation. `disableOnInteraction`
            // stays false so a manual swipe does not kill the rotation, and
            // `pauseOnMouseEnter` freezes the rail while the advisor is
            // reading a card instead of sliding it away mid-read.
            autoplay={
              autoplayOn
                ? {
                    delay: 3500,
                    disableOnInteraction: false,
                    pauseOnMouseEnter: true
                  }
                : false
            }
            // The manual path: a gold hairline the advisor can drag at any
            // width. `hide: false` keeps it visible so the rail advertises
            // that more listings sit beyond the first six.
            scrollbar={{ draggable: true, hide: false }}
            // At the twelfth card the rail rewinds to the first instead of
            // dead-ending: with `slidesPerView="auto"` and a 12-slide window
            // `loop` would need cloned slides, while `rewind` gives the same
            // endless-showcase feel with no duplicates.
            rewind
            // The rail is inside a page that already scrolls, so a vertical
            // gesture must never be captured as a slide.
            touchReleaseOnEdges
            grabCursor
            keyboard={{ enabled: true }}
            a11y={{ enabled: true }}
            className="lux-swiper -mx-1 px-1 pb-1"
          >
            {visible.map((property, i) => (
              <SwiperSlide
                key={property.id}
                // Swiper needs the slide to be the sizing element; a wrapper div
                // would add a level between the flex track and the card.
                className={cn(
                  "w-[min(78vw,300px)] sm:w-[300px]",
                  i === visible.length - 1 && "me-7"
                )}
              >
                <PropertyCard
                  property={property}
                  variant={variant}
                  index={i}
                  marketMedian={
                    marketMedians
                      ? marketMedianFor(property, marketMedians)
                      : undefined
                  }
                  leadAction={<AddToLeadsButton property={property} />}
                />
              </SwiperSlide>
            ))}
          </Swiper>
        </div>
      )}
    </section>
  );
}
