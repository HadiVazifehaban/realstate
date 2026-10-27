'use client';

import { parseAsArrayOf, parseAsString, useQueryStates } from 'nuqs';

/** URL is authoritative, including an empty selection (the whole country).
 * Activity-city preferences remain separate: they must not silently narrow a
 * multi-city market or turn "all" back into Tehran after refresh.
 */
export function useLocationFilter() {
  const [location, setLocation] = useQueryStates({
    city: parseAsArrayOf(parseAsString).withDefault([])
  });
  return { cities: location.city, setCities: (city: string[]) => setLocation({ city }) };
}