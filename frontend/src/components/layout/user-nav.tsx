"use client";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { UserAvatarProfile } from "@/components/user-avatar-profile";
import { MobileProfileSheet } from "@/components/navigation/MobileProfileSheet";
import { useAuthContext, useAuthSignOut } from "@/hooks/use-auth";
import { useIsMobile } from "@/hooks/use-mobile";
import { useRouter } from "next/navigation";
export function UserNav() {
  const { user, saasTier } = useAuthContext();
  const signOut = useAuthSignOut();
  const router = useRouter();
  const isMobile = useIsMobile();
  if (user) {
    if (isMobile) {
      return (
        <MobileProfileSheet
          user={user}
          planLabel={saasTier}
          onSignOut={() => signOut({ redirectUrl: "/auth/sign-in" })}
        />
      );
    }

    return (
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" className="relative h-8 w-8 rounded-full" />}
        >
          <UserAvatarProfile user={user} />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" align="end" sideOffset={10}>
          <DropdownMenuGroup>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm leading-none font-medium">
                  {user.fullName || "کاربر شکارچی"}
                </p>
                <p className="text-muted-foreground text-xs leading-none">
                  {user.emailAddresses[0]?.emailAddress || user.phoneNumber || "حساب کاربری"}
                </p>
              </div>
            </DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => router.push("/dashboard/profile")}>
              پروفایل
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/dashboard/billing")}>
              اشتراک و پرداخت
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/dashboard/network/commissions")}>
              کمیسیون و تسویه
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => signOut({ redirectUrl: "/auth/sign-in" })}>
              خروج امن از حساب
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
}
