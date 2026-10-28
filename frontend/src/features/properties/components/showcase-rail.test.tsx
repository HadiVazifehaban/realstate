import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ShowcaseRail } from './showcase-rail';

vi.mock('swiper/react', () => ({
  Swiper: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SwiperSlide: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));
vi.mock('./property-card', () => ({ PropertyCard: () => <article>ملک نمونه</article> }));
vi.mock('./add-to-leads-button', () => ({ AddToLeadsButton: () => null }));

describe('ShowcaseRail navigation', () => {
  it('keeps previous and next navigation controls on both rails', () => {
    const { container } = render(
      <ShowcaseRail
        title='ویترین خرید'
        subtitle='فروش'
        variant='buy'
        items={[]}
        total={0}
        loading={false}
        viewAllHref='/dashboard/properties'
      />
    );

    expect(screen.getByRole('button', { name: 'قبلی' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'بعدی' })).toBeTruthy();
    expect(container.querySelectorAll('.lux-nav-pill')).toHaveLength(3);
  });
});