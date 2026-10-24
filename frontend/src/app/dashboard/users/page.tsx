import PageContainer from '@/components/layout/page-container';
import UserListingPage from '@/features/users/components/user-listing';
import { searchParamsCache } from '@/lib/searchparams';
import type { SearchParams } from 'nuqs/server';
import { usersInfoContent } from '@/features/users/info-content';
import { UserFormSheetTrigger } from '@/features/users/components/user-form-sheet';

export const metadata = {
  title: "کاربران و نقش‌ها"
};

type PageProps = {
  searchParams: Promise<SearchParams>;
};

export default async function UsersPage(props: PageProps) {
  const searchParams = await props.searchParams;
  searchParamsCache.parse(searchParams);

  return (
    <PageContainer
      pageTitle='کاربران و نقش‌ها'
      pageDescription='مدیریت کاربران دفتر و توزیع سطوح دسترسی'
      infoContent={usersInfoContent}
      pageHeaderAction={<UserFormSheetTrigger />}
    >
      {/* The listing renders the role histogram above the table, sharing one
          query so the counts can never disagree with the visible rows. */}
      <UserListingPage showRoleBreakdown />
    </PageContainer>
  );
}
