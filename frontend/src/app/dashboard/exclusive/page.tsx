"use client";

import PageContainer from '@/components/layout/page-container';
import { AuthBypassNotice } from '@/components/layout/auth-bypass-notice';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useOrganization, Show } from '@clerk/nextjs';
import { Icons } from '@/components/icons';
import { Alert, AlertDescription } from '@/components/ui/alert';
import Link from 'next/link';
import { CLERK_ENABLED } from '@/lib/utils';

export default function ExclusivePage() {
  // `useOrganization` and `<Show when={{ plan }}>` both read Clerk context,
  // which is not mounted under the bypass or under Keycloak, so keep them off
  // this render path.
  if (!CLERK_ENABLED) {
    return (
      <PageContainer>
        <AuthBypassNotice
          title='بخش ویژه'
          description='در حالت توسعه (بدون احراز هویت) فعال نیست. این بخش برای دفاتر دارای اشتراک Pro در دسترس است.'
        />
      </PageContainer>
    );
  }

  return <ClerkExclusivePage />;
}

function ClerkExclusivePage() {
  const { organization, isLoaded } = useOrganization();

  return (
    <PageContainer isLoading={!isLoaded}>
      <Show
        when={{ plan: "pro" }}
        fallback={
          <div className='flex h-full items-center justify-center'>
            <Alert>
              <Icons.lock className='h-5 w-5 text-yellow-600' />
              <AlertDescription>
                <div className='mb-1 text-lg font-semibold'>Pro Plan Required</div>
                <div className='text-muted-foreground'>
                  This page is only available to organizations on the{" "}
                  <span className='font-semibold'>Pro</span> plan.
                  <br />
                  Upgrade your subscription in&nbsp;
                  <Link className='underline' href='/dashboard/billing'>
                    Billing &amp; Plans
                  </Link>
                  .
                </div>
              </AlertDescription>
            </Alert>
          </div>
        }
      >
        <div className='space-y-6'>
          <div>
            <h1 className='flex items-center gap-2 text-3xl font-bold tracking-tight'>
              <Icons.badgeCheck className='h-7 w-7 text-green-600' />
              Exclusive Area
            </h1>
            <p className='text-muted-foreground'>
              Welcome, <span className='font-semibold'>{organization?.name}</span>! This page
              contains exclusive features for Pro plan organizations.
            </p>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Thank You for Checking Out the Exclusive Page</CardTitle>
              <CardDescription>
                This means you belong to an organization subscribed to the Pro plan.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className='text-lg'>Have a wonderful day!</div>
            </CardContent>
          </Card>
        </div>
      </Show>
    </PageContainer>
  );
}
