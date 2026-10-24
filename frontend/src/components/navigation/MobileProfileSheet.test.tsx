import * as React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MobileProfileSheet } from "./MobileProfileSheet";

const subscriptionState = vi.hoisted(() => ({ error: false, refetch: vi.fn() }));

vi.mock("@/lib/utils", () => ({ KEYCLOAK_ENABLED: true }));
vi.mock("@/hooks/use-current-subscription", () => ({
  useCurrentSubscription: () => ({
    data: subscriptionState.error
      ? undefined
      : {
          title: "پلن طلایی",
          listing_quota: 50,
          sms_quota: 30,
          is_unlimited: false,
          usage: {}
        },
    isPending: false,
    isError: subscriptionState.error,
    state: subscriptionState.error ? "error" : "success",
    refetch: subscriptionState.refetch
  })
}));

vi.mock("next/link", async () => {
  const React = await import("react");
  return {
    default: ({ href, onClick, children, ...props }: React.ComponentProps<"a">) =>
      React.createElement(
        "a",
        {
          href,
          onClick: (event: React.MouseEvent<HTMLAnchorElement>) => {
            event.preventDefault();
            onClick?.(event);
          },
          ...props
        },
        children
      )
  };
});

vi.mock("@/components/ui/button", async () => {
  const React = await import("react");
  return {
    Button: React.forwardRef<HTMLButtonElement, React.ComponentProps<"button">>(
      ({ children, ...props }, ref) => React.createElement("button", { ...props, ref }, children)
    )
  };
});

vi.mock("@/components/ui/avatar", async () => {
  const React = await import("react");
  return {
    Avatar: ({ children, ...props }: React.ComponentProps<"div">) =>
      React.createElement("div", props, children),
    AvatarFallback: ({ children, ...props }: React.ComponentProps<"span">) =>
      React.createElement("span", props, children),
    AvatarImage: (props: React.ComponentProps<"img">) => React.createElement("img", props)
  };
});

vi.mock("@/components/ui/drawer", async () => {
  const React = await import("react");
  type DrawerContextValue = { open: boolean; onOpenChange: (open: boolean) => void };
  const Context = React.createContext<DrawerContextValue>({
    open: false,
    onOpenChange: () => undefined
  });
  const passthrough =
    (tag: "div" | "h2" | "p") =>
    ({ children, ...props }: React.HTMLAttributes<HTMLElement>) =>
      React.createElement(tag, props, children);

  return {
    Drawer: ({ open, onOpenChange, children }: React.PropsWithChildren<DrawerContextValue>) =>
      React.createElement(Context.Provider, { value: { open, onOpenChange } }, children),
    DrawerTrigger: ({
      render,
      children
    }: {
      render: React.ReactElement;
      children: React.ReactNode;
    }) => {
      const { onOpenChange } = React.useContext(Context);
      return React.cloneElement(
        render as React.ReactElement<React.ButtonHTMLAttributes<HTMLButtonElement>>,
        { onClick: () => onOpenChange(true) },
        children
      );
    },
    DrawerContent: ({ children }: React.HTMLAttributes<HTMLDivElement>) => {
      const { open, onOpenChange } = React.useContext(Context);
      if (!open) return null;
      return React.createElement(
        React.Fragment,
        null,
        React.createElement("button", {
          type: "button",
          "data-testid": "overlay",
          onClick: () => onOpenChange(false)
        }),
        React.createElement("div", { role: "dialog" }, children)
      );
    },
    DrawerClose: ({
      render,
      children
    }: {
      render: React.ReactElement;
      children: React.ReactNode;
    }) => {
      const { onOpenChange } = React.useContext(Context);
      return React.cloneElement(
        render as React.ReactElement<React.ButtonHTMLAttributes<HTMLButtonElement>>,
        { onClick: () => onOpenChange(false) },
        children
      );
    },
    DrawerHeader: passthrough("div"),
    DrawerDescription: passthrough("p"),
    DrawerTitle: passthrough("h2"),
    DrawerSwipeHandle: () => {
      const { onOpenChange } = React.useContext(Context);
      return React.createElement("div", {
        "data-testid": "swipe-handle",
        onTouchEnd: () => onOpenChange(false)
      });
    }
  };
});

describe("MobileProfileSheet", () => {
  const user = {
    fullName: "کاربر آزمایشی",
    phoneNumber: "+989391234567",
    imageUrl: "/avatar.png",
    emailAddresses: []
  };

  beforeEach(() => {
    subscriptionState.error = false;
    subscriptionState.refetch.mockClear();
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("shows live plan limits, unknown usage and Persian phone digits without invented counts", () => {
    render(<MobileProfileSheet user={user} onSignOut={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی پروفایل" }));

    expect(screen.queryByText("شماره نامشخص")).toBeNull();
    expect(screen.getByText("۰۹۳۹۱۲۳۴۵۶۷")).not.toBeNull();
    expect(screen.getByText("سهمیه پلن: ۵۰ آگهی")).not.toBeNull();
    expect(screen.getByText("رادار لید: ۳۰ پیامک")).not.toBeNull();
    expect(screen.getAllByText("مصرف: نامشخص (در انتظار API)")).toHaveLength(2);
  });

  it("keeps developer platform disabled and identifies unavailable wallet balance", () => {
    render(<MobileProfileSheet user={user} onSignOut={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی پروفایل" }));

    const developerEntry = screen
      .getByText("پلتفرم توسعه‌دهندگان")
      .closest('[aria-disabled="true"]');
    expect(developerEntry?.getAttribute("title")).toBe("به‌زودی؛ در نسخه بعد فعال می‌شود.");
    expect(developerEntry?.classList.contains("cursor-not-allowed")).toBe(true);
    const walletEntry = screen.getByText("کیف پول دفتری").closest('[aria-disabled="true"]');
    expect(walletEntry).not.toBeNull();
    expect(screen.getByText("ناموجود")).not.toBeNull();
    expect(screen.getByText("موجودی کیف پول هنوز از سمت سرور ارائه نشده است.")).not.toBeNull();
  });

  it("shows a retry action when the subscription API fails", () => {
    subscriptionState.error = true;
    render(<MobileProfileSheet user={user} onSignOut={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی پروفایل" }));

    expect(screen.getByText("خطا در دریافت وضعیت اشتراک")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    expect(subscriptionState.refetch).toHaveBeenCalledOnce();
  });

  it("closes when an item is selected, the overlay is clicked or the sheet is swiped down", () => {
    const { rerender } = render(<MobileProfileSheet user={user} onSignOut={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی پروفایل" }));
    fireEvent.click(screen.getByRole("link", { name: /صورتحساب و تمدید اشتراک/ }));
    expect(screen.queryByRole("dialog")).toBeNull();

    rerender(<MobileProfileSheet user={user} onSignOut={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی پروفایل" }));
    fireEvent.click(screen.getByTestId("overlay"));
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی پروفایل" }));
    fireEvent.touchEnd(screen.getByTestId("swipe-handle"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
