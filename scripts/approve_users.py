#!/usr/bin/env python3
"""
Interactive script to list and approve users from Keycloak.
Run this script inside the backend container.
"""

import sys
import asyncio
sys.path.insert(0, '/app')

from app.core.config import get_settings
from app.services import keycloak_admin


async def main():
    settings = get_settings()

    print("=" * 60)
    print("لیست کاربران Keycloak")
    print("=" * 60)

    # Get all users
    users = await keycloak_admin.list_directory_users(settings)

    if not users:
        print("هیچ کاربری یافت نشد.")
        return

    # Print user list
    print(f"\n{'ID':<40} {'نام کاربری':<20} {'ایمیل':<30} {'نقش‌ها'}")
    print("-" * 120)

    user_list = []
    for user in users:
        roles = list(user.realm_roles)
        role_str = ", ".join(roles) if roles else "بدون نقش"
        print(f"{user.id:<40} {user.username:<20} {user.email:<30} {role_str}")
        user_list.append(user)

    print("\n" + "=" * 60)
    print("برای تایید یک کاربر، ID آن را وارد کنید.")
    print("برای تغییر نقش، ID و نقش را با فاصله وارد کنید (مثال: USER_ID ROLE_OWNER)")
    print("برای خروج، q را وارد کنید.")
    print("=" * 60)

    while True:
        user_input = input("\n> ").strip()

        if user_input.lower() == 'q':
            print("خروج...")
            break

        if not user_input:
            continue

        parts = user_input.split()

        if len(parts) == 1:
            # Just approve (set VERIFIED status - but this doesn't work in Keycloak)
            user_id = parts[0]
            print(f"⚠️  تایید KYC در Keycloak کار نمی‌کند.")
            print(f"   به جای آن، نقش کاربر را تغییر دهید.")
            print(f"   مثال: {user_id} ROLE_OWNER")
        elif len(parts) == 2:
            user_id, role_name = parts
            try:
                print(f"در حال تغییر نقش کاربر به {role_name}...")
                await keycloak_admin._set_realm_roles(settings, user_id, [role_name])
                print(f"✅ نقش کاربر به {role_name} تغییر یافت!")
            except Exception as e:
                print(f"❌ خطا: {e}")
        else:
            print("فرمت اشتباه است. مثال: USER_ID ROLE_NAME")


if __name__ == "__main__":
    asyncio.run(main())
