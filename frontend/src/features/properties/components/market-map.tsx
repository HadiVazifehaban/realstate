"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { TILE_URL, tileErrorMessage } from "@/features/map/config/tiles";

import type { MarketBubble } from "./market-map-canvas";

/**
 * Leaflet touches `window` at module scope, so the canvas can only load in the
 * browser. In the App Router that has to happen inside a client component.
 */
const MarketMapCanvas = dynamic(() => import("./market-map-canvas"), {
  ssr: false,
  loading: () => <Skeleton className="size-full" />
});

export function MarketMap({
  bubbles,
  selectedId,
  onSelect,
  height
}: {
  bubbles: MarketBubble[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  /** Height of the map. When omitted the map flexes to fill the remaining
   * column height (used by the AVM two-column layout). When set, a fixed
   * pixel height is applied instead. */
  height?: number;
}) {
  // Tile failures arrive as a window event: Leaflet's TileLayer is built inside
  // react-leaflet, out of reach of React state here.
  const [tilesDown, setTilesDown] = useState(false);

  useEffect(() => {
    const onError = () => setTilesDown(true);
    const onLoad = () => setTilesDown(false);
    window.addEventListener("tiles:error", onError);
    window.addEventListener("tiles:load", onLoad);
    return () => {
      window.removeEventListener("tiles:error", onError);
      window.removeEventListener("tiles:load", onLoad);
    };
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div
        className="border-border relative isolate min-h-[280px] overflow-hidden rounded-xl border flex-1"
        {...(height ? { style: { height } } : {})}
      >
        <MarketMapCanvas bubbles={bubbles} selectedId={selectedId} onSelect={onSelect} />
      </div>

      {tilesDown && (
        <Alert variant="destructive">
          <AlertTitle>سرویس تایل در دسترس نیست</AlertTitle>
          <AlertDescription>
            {tileErrorMessage()}
            <span className="mt-1 block font-mono text-xs" dir="ltr">
              {TILE_URL}
            </span>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
