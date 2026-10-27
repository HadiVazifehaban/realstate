import * as React from 'react';
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ShowcaseSection } from './showcase-section';

const state = vi.hoisted(() => ({ cities: ['اردبیل', 'پارس آباد', 'خلخال'], query: vi.fn() }));
vi.mock('../hooks/use-location-filter', () => ({
  useLocationFilter: () => ({ cities: state.cities })
}));
vi.mock('../hooks', () => ({
  useProperties: (filters: unknown) => {
    state.query(filters);
    return { data: { items: [], count: 0 }, isPending: false, isError: false };
  }
}));
vi.mock('./showcase-filter-bar', () => ({
  ShowcaseFilterBar: () => null,
  categoryTypes: () => undefined
}));
vi.mock('./showcase-rail', () => ({ ShowcaseRail: () => null }));

describe('showcase shared location scope', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  it('queries the selected province cities, then removes the restriction for all cities', () => {
    const props = {
      category: 'all' as React.ComponentProps<typeof ShowcaseSection>['category'],
      onCategory: vi.fn(), priceB: [0, 20] as [number, number], onPriceB: vi.fn(),
      area: [0, 500] as [number, number], onArea: vi.fn(), advanced: {},
      onAdvanced: vi.fn(), dealTypes: [], onDealTypes: vi.fn()
    };
    const { rerender } = render(<ShowcaseSection {...props} />);
    expect(state.query).toHaveBeenLastCalledWith(expect.objectContaining({
      city: ['اردبیل', 'پارس آباد', 'خلخال'], limit: 120
    }));
    state.cities = [];
    rerender(<ShowcaseSection {...props} />);
    expect(state.query).toHaveBeenLastCalledWith(expect.objectContaining({ city: undefined }));
  });
});