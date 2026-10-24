'use client';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription
} from '@/components/ui/card';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';
import type { FeaturedListing } from '../api/types';

interface FeaturedListingsProps {
  listings: FeaturedListing[];
}

export function FeaturedListings({ listings }: FeaturedListingsProps) {
  const formatPrice = (price: number) => {
    return (price / 1000000).toFixed(0) + ' میلیون';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <Icons.circleCheck className='size-5 text-[#e5a87b]' />
          آگهی‌های ویژه
        </CardTitle>
        <CardDescription>آگهی‌های پر بازدید و محبوب</CardDescription>
      </CardHeader>
      <div className='p-6 space-y-4'>
        {listings.map((listing) => (
          <div key={listing.id} className='flex items-start gap-4 p-3 rounded-lg border border-[#ffd8be]/20 bg-white/[0.03] hover:border-[#e5a87b]/50 hover:bg-[#e5a87b]/10 transition-all'>
            <div className='w-16 h-16 rounded-lg bg-[#ffd8be]/20 flex items-center justify-center flex-shrink-0'>
              <Icons.building className='size-8 text-[#e5a87b]' />
            </div>
            <div className='flex-1 min-w-0'>
              <p className='text-sm font-semibold truncate'>{listing.title}</p>
              <div className='flex items-center gap-2 mt-1'>
                <span className='text-xs text-muted-foreground'>{listing.city}</span>
                <span className='text-xs text-[#e5a87b]'>{listing.type}</span>
                <span className='text-xs text-blue-600'>{listing.status}</span>
              </div>
              <div className='flex items-center justify-between mt-2'>
                <span className='text-sm font-bold text-[#e5a87b]'>{formatPrice(listing.price)}</span>
                <span className='text-xs text-muted-foreground flex items-center gap-1'>
                  <Icons.eye className='size-3' />
                  {listing.views.toLocaleString('fa-IR')}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
