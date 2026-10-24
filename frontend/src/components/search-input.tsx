'use client';
import { Icons } from '@/components/icons';
import { Input } from './ui/input';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { cn } from '@/lib/utils';

export default function SearchInput() {
  const [searchQuery, setSearchQuery] = useState('');
  const router = useRouter();
  const pathname = usePathname();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // If not on properties page, navigate there with search query
      if (pathname !== '/dashboard/properties') {
        router.push(`/dashboard/properties?search=${encodeURIComponent(searchQuery.trim())}`);
      } else {
        // Already on properties page, update URL with search query
        router.push(`/dashboard/properties?search=${encodeURIComponent(searchQuery.trim())}`);
      }
    }
  };

  return (
    <form onSubmit={handleSearch} className='w-full'>
      <div className='relative'>
        <Icons.search className='absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
        <Input
          type='text'
          placeholder='جستجوی آگهی...'
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={cn(
            'h-9 w-full rounded-lg bg-muted/50 border-border',
            'pr-9 pl-3 text-sm',
            'placeholder:text-muted-foreground/70',
            'focus-visible:bg-background',
            'w-48 lg:w-64'
          )}
        />
      </div>
    </form>
  );
}
