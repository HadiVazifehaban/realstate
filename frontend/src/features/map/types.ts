export interface LatLngLiteral {
  lat: number;
  lng: number;
}

export interface MapPin {
  id: string;
  lat: number;
  lng: number;
  /** Shown in the tooltip. Never put owner contact here -- it is PII. */
  label: string;
  /** bargain = under market, overpriced = over market. */
  tone?: 'bargain' | 'fair' | 'overpriced';
}
