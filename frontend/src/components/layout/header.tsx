import React from 'react';
import { SidebarTrigger } from '../ui/sidebar';
import { Separator } from '../ui/separator';
import { Breadcrumbs } from '../breadcrumbs';
import SearchInput from '../search-input';
import { ThemeSelector } from '../themes/theme-selector';
import { ThemeModeToggle } from '../themes/theme-mode-toggle';
import CtaLogin from './cta-login';
import { NotificationCenter } from '@/features/notifications/components/notification-center';
import HeaderLocationPicker from './header-location-picker';
import { UserNav } from './user-nav';

export default function Header() {
  return (
    <header className='bg-background/80 sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-4 px-4 backdrop-blur-md border-b border-border/50 md:h-14 md:px-6'>
      {/* بخش راست: سایدبار و مسیر ناوبری */}
      <div className='flex items-center gap-3'>
        <SidebarTrigger className='-ms-1 hidden md:inline-flex' />
        <Separator orientation='vertical' className='hidden h-6 md:block' />
        <Breadcrumbs />
      </div>

      {/* بخش چپ: ابزارها */}
      <div className='flex items-center gap-2 md:gap-3'>
        <HeaderLocationPicker />
        <div className='hidden lg:flex'>
          <SearchInput />
        </div>
        <ThemeModeToggle />
        <div className='hidden sm:block'>
          <ThemeSelector />
        </div>
        <CtaLogin />
        <UserNav />
        <NotificationCenter />
      </div>
    </header>
  );
}
