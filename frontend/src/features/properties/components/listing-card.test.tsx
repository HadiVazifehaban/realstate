import * as React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ListingCard } from "./listing-card";
import type { PropertySummary } from "../types";

const property: PropertySummary = {
  id: "test-property",
  title: "آپارتمان ولنجک",
  property_type: "APARTMENT",
  deal_type: "SALE",
  status: "ACTIVE",
  neighborhood: "ولنجک",
  city: "تهران",
  area: 120,
  rooms: 2,
  total_price: 24000000000,
  price_per_meter: 200000000,
  valuation_status: "BARGAIN",
  valuation_deviation_pct: -5,
  valuation_median_price_per_meter: null,
  valuation_sample_count: null,
  latitude: null,
  longitude: null,
  exact_pin: false,
  privacy_radius_m: 500,
  agent_name: null,
  agency_name: null,
  source_ref: null,
  source: "DIVAR",
  submitter_type: null,
  floor: null,
  total_floors: null,
  year_built: null,
  has_elevator: false,
  has_parking: true,
  has_storage: false,
  has_balcony: false,
  deposit_amount: null,
  monthly_rent: null,
  updated_at: null,
  description: "",
  cover_url: null,
  images_count: 0
};

describe("ListingCard density", () => {
  afterEach(cleanup);

  it("uses a smaller cover and body only when compact is requested", () => {
    const { container, rerender } = render(<ListingCard property={property} compact />);
    expect(container.querySelector(".aspect-video")).not.toBeNull();
    expect(container.querySelector(".p-2")).not.toBeNull();
    expect(screen.getByRole("link").getAttribute("href")).toBe(
      "/dashboard/properties/test-property"
    );
    expect(screen.getByText("پارکینگ")).toBeDefined();
    rerender(<ListingCard property={property} />);
    expect(container.querySelector(".aspect-video")).toBeNull();
    expect(container.querySelector(".aspect-4\\/3")).not.toBeNull();
  });
});
