#!/usr/bin/env python3
"""
Script to list users and their roles in Keycloak.
Then guide the user to manually change roles in Keycloak admin console.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.services import keycloak_admin

async def main():
    settings = get_settings()
    
    print("Fetching users from Keycloak...")
    users = await keycloak_admin.list_directory_users(settings)
    
    print(f"\nFound {len(users)} users:\n")
    
    for user in users:
        print(f"Username: {user.username}")
        print(f"Name: {user.first_name} {user.last_name}")
        print(f"Email: {user.email}")
        print(f"Role: {user.role}")
        print(f"Realm Roles: {', '.join(user.realm_roles)}")
        print(f"ID: {user.id}")
        print("-" * 50)
    
    print("\n=== INSTRUCTIONS TO CHANGE ROLES ===")
    print("1. Go to Keycloak Admin Console:")
    print(f"   {settings.keycloak_public_url}/admin")
    print("2. Log in with admin credentials")
    print("3. Go to: Realm -> Users -> Click on the user")
    print("4. Go to the 'Role Mappings' tab")
    print("5. Under 'Realm Roles', assign or remove roles:")
    print("   - To be 'شخص حقیقی' (register property as owner):")
    print("     * Add: ROLE_OWNER")
    print("     * Remove: ROLE_SENIOR_BROKER, ROLE_JUNIOR_BROKER, ROLE_AGENCY_MANAGER, ROLE_SUPERVISOR, ROLE_ADMIN")
    print("   - To be 'بنگاه' (register property as agency):")
    print("     * Add: ROLE_SENIOR_BROKER or ROLE_JUNIOR_BROKER")
    print("     * Remove: ROLE_OWNER")
    print("6. Click 'Save'")
    print("7. Log out and log in again in the application")

if __name__ == '__main__':
    asyncio.run(main())
