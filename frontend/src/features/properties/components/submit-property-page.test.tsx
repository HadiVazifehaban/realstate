import { fireEvent, render, screen } from '@testing-library/react';
import * as React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  mutate: vi.fn(),
  roles: ['ROLE_ADMIN'] as string[],
  locationChanged: false
}));

vi.mock('../hooks', () => ({
  useSubmitProperty: () => ({ mutate: mocks.mutate, isPending: false, isError: false }),
  useUploadPropertyMedia: () => ({ mutate: vi.fn(), isPending: false })
}));

vi.mock('@/hooks/use-auth', () => ({ useRealmRoles: () => mocks.roles }));
vi.mock('@/components/OsmLocationPicker', () => ({
  OsmLocationPicker: ({ onChange }: { onChange: (lat: number, lng: number) => void }) => {
    const [position, setPosition] = React.useState({ lat: 35.6892, lng: 51.389 });
    return (
      <button
        type='button'
        onClick={() => {
          const next = { lat: 35.7, lng: 51.4 };
          setPosition(next);
          mocks.locationChanged = true;
          onChange(next.lat, next.lng);
        }}
      >
        {mocks.locationChanged ? `${position.lat},${position.lng}` : 'انتخاب موقعیت آزمایشی'}
      </button>
    );
  }
}));
vi.mock('./property-media-uploader', () => ({
  PropertyMediaUploader: () => <div>آپلودر آزمایشی</div>
}));
vi.mock('@/components/layout/page-container', () => ({
  default: ({ children }: { children: React.ReactNode }) => <main>{children}</main>
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import SubmitPropertyPage from './submit-property-page';

describe('SubmitPropertyPage', () => {
  beforeEach(() => {
    mocks.mutate.mockReset();
    mocks.roles = ['ROLE_ADMIN'];
    mocks.locationChanged = false;
  });

  it('keeps units out of numeric inputs and parses Persian digits for area, year and price', () => {
    render(<SubmitPropertyPage />);
    const area = screen.getByLabelText('متراژ') as HTMLInputElement;
    const year = screen.getByLabelText('سال ساخت') as HTMLInputElement;
    const price = screen.getByLabelText('قیمت کل (تومان)') as HTMLInputElement;

    fireEvent.change(area, { target: { value: '۱۲۵' } });
    fireEvent.change(year, { target: { value: '۱۳۹۸' } });
    fireEvent.change(price, { target: { value: '۲۵۰۰۰۰۰۰۰۰' } });

    expect(area.value).toBe('۱۲۵');
    expect(year.value).toBe('۱۳۹۸');
    expect(price.value).toContain('۲,۵۰۰,۰۰۰,۰۰۰');
    expect(screen.queryByText('متر مربع', { selector: 'span' })).toBeNull();
    expect(screen.queryByText('تومان', { selector: 'span' })).toBeNull();
  });

  it('does not submit until a valid map pin, title, and sale price are provided', () => {
    mocks.roles = ['ROLE_ADMIN'];
    render(<SubmitPropertyPage />);
    const submitButtons = screen.getAllByRole('button', { name: 'ثبت ملک در دفتر' });
    expect(submitButtons.some((button) => (button as HTMLButtonElement).disabled)).toBe(true);

    fireEvent.click(screen.getAllByRole('button', { name: 'انتخاب موقعیت آزمایشی' })[0]!);
    fireEvent.change(screen.getByLabelText('عنوان آگهی'), { target: { value: 'آپارتمان تستی' } });
    expect(submitButtons.some((button) => (button as HTMLButtonElement).disabled)).toBe(true);

    fireEvent.change(screen.getByLabelText('قیمت کل (تومان)'), { target: { value: '۲۰۰۰۰۰۰۰۰۰' } });
    expect(submitButtons.some((button) => !(button as HTMLButtonElement).disabled)).toBe(true);
    expect(mocks.mutate).not.toHaveBeenCalled();
  });
});