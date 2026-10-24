import * as React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ mobile: true }));

vi.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => state.mobile }));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => ({
    user: { fullName: "کاربر", emailAddresses: [{ emailAddress: "user@example.test" }] },
    saasTier: "طلایی"
  }),
  useAuthSignOut: () => vi.fn()
}));
vi.mock("@/components/navigation/MobileProfileSheet", () => ({
  MobileProfileSheet: () => <div data-testid="mobile-profile-sheet">پروفایل موبایل</div>
}));
vi.mock("@/components/user-avatar-profile", () => ({
  UserAvatarProfile: () => <span>آواتار</span>
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/ui/button", () => ({
  Button: ({ children }: React.PropsWithChildren) => <button>{children}</button>
}));
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  DropdownMenuGroup: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  DropdownMenuItem: ({ children }: React.PropsWithChildren) => <button>{children}</button>,
  DropdownMenuLabel: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuTrigger: ({ children }: React.PropsWithChildren) => <div>{children}</div>
}));

import { UserNav } from "./user-nav";

describe("UserNav responsive profile menu", () => {
  afterEach(cleanup);

  beforeEach(() => {
    state.mobile = true;
  });

  it("renders the bottom sheet below the mobile breakpoint", () => {
    render(<UserNav />);
    expect(screen.getByTestId("mobile-profile-sheet")).not.toBeNull();
    expect(screen.queryByText("پروفایل", { selector: "button" })).toBeNull();
  });

  it("keeps the desktop dropdown and does not render the mobile sheet at desktop width", () => {
    state.mobile = false;
    render(<UserNav />);
    expect(screen.queryByTestId("mobile-profile-sheet")).toBeNull();
    expect(screen.getByText("پروفایل", { selector: "button" })).not.toBeNull();
  });
});
