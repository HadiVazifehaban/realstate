import * as React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MarketList, type MarketRow } from "./market-list";

const rows: MarketRow[] = [
  {
    id: "ولنجک",
    neighborhood: "ولنجک",
    city: "تهران",
    value: "۲۰۰,۰۰۰,۰۰۰ تومان/متر",
    files: "۱۲",
    color: "#22c55e",
    bargainShare: 0.25
  },
  {
    id: "نام محله بسیار طولانی برای نمایش در ستون فشرده",
    neighborhood: "نام محله بسیار طولانی برای نمایش در ستون فشرده",
    city: "تهران",
    value: "۱۵۰,۰۰۰,۰۰۰ تومان/متر",
    files: "۸",
    color: "#3b82f6",
    bargainShare: 0
  }
];

describe("MarketList compact neighbourhood ranking", () => {
  afterEach(cleanup);

  it("keeps the RTL rows inside a padded internal scroll region", () => {
    const { container } = render(
      <MarketList rows={rows} onSelect={vi.fn()} emptyMessage="بدون محله" />
    );
    const list = container.firstElementChild!;
    expect(list.getAttribute("dir")).toBe("rtl");
    for (const className of ["min-h-0", "flex-1", "overflow-y-auto", "p-2", "space-y-1.5"]) {
      expect(list.classList.contains(className)).toBe(true);
    }
    expect(screen.getByText("۱")).toBeDefined();
    expect(screen.getByText("۱۲ فایل")).toBeDefined();
    expect(screen.getByText("۲۵٪ ارزان")).toBeDefined();
    expect(screen.queryByText("تومان/متر", { exact: true })).toBeNull();
    const name = screen.getByText(rows[1].neighborhood);
    expect(name.classList.contains("truncate")).toBe(true);
    expect(name.getAttribute("title")).toBe(rows[1].neighborhood);
  });

  it("preserves accessible selection and the map colour indicator", () => {
    const onSelect = vi.fn();
    render(
      <MarketList rows={rows} selectedId="ولنجک" onSelect={onSelect} emptyMessage="بدون محله" />
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons[0].getAttribute("aria-current")).toBe("true");
    expect(buttons[0].querySelector("[style]")?.getAttribute("style")).toContain(
      "background-color"
    );
    fireEvent.click(buttons[1]);
    expect(onSelect).toHaveBeenCalledWith(rows[1].id);
  });

  it.each(["۸ فایل", "۲۵٫۵٪", "۳ میلیون تومان"])(
    "does not mislabel a non-price metric: %s",
    (value) => {
      render(
        <MarketList rows={[{ ...rows[0], value }]} onSelect={vi.fn()} emptyMessage="بدون محله" />
      );
      expect(screen.getByText(value)).toBeDefined();
      expect(screen.queryByText(/تومان\/متر/)).toBeNull();
    }
  );

  it("renders the supplied empty state without placeholder neighbourhoods", () => {
    render(<MarketList rows={[]} onSelect={vi.fn()} emptyMessage="محله‌ای با این فیلترها نیست." />);
    expect(screen.getByText("محله‌ای با این فیلترها نیست.")).toBeDefined();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
