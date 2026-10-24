'use client';

import * as React from 'react';
import type { Map as LeafletMap } from 'leaflet';
import { useCityStore } from '@/store/useCityStore';

/**
 * با تغییر شهر فعال شکارچی، دوربین نقشهٔ Leaflet را به مرکز شهر می‌برد.
 * @param getMap تابعی که نمونهٔ فعلی نقشه را برمی‌گرداند (ref پدر).
 */
export function useCityMapSync(getMap: () => LeafletMap | null | undefined): void {
  const activeCity = useCityStore((s) => s.activeCity);

  React.useEffect(() => {
    if (!activeCity) return;
    const map = getMap();
    if (!map) return;
    map.flyTo(activeCity.center, activeCity.zoom, { duration: 1.5 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCity?.id]);
}
