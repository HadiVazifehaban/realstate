"use client";

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { cn, formatPricePerMeter, formatToman } from '@/lib/utils';
import {
  DEAL_TYPE_LABELS,
  PROPERTY_TYPE_LABELS,
  VALUATION_BADGE_VARIANT,
  VALUATION_LABELS,
  formatDeviation
} from '../utils/labels';
import type { PropertySummary } from '../types';

interface PropertyLeadCardProps {
  property: PropertySummary;
}

export function PropertyLeadCard({ property }: PropertyLeadCardProps) {
  const isBargain = property.valuation_status ==='BARGAIN';
  const location = [property.neighborhood, property.city].filter(Boolean).join("، ");
  /* «بدون مرجع» is the absence of a verdict, not a verdict, and a chip that
     labels the missing data reads as noise next to the rows that carry one.
     Only the three real verdicts get a chip. */
  const hasVerdict = property.valuation_status !== 'UNKNOWN';

  return (
    <Card
      size='sm'
      className={cn("gap-3 transition-shadow", isBargain && "ring-primary/40 ring-2")}
    >
      <CardHeader>
        <CardTitle className='line-clamp-1'>
          {property.title || `${PROPERTY_TYPE_LABELS[property.property_type]} در ${location}`}
        </CardTitle>
        <CardDescription className='line-clamp-1'>
          {location || "موقعیت نامشخص"} · {DEAL_TYPE_LABELS[property.deal_type]}
        </CardDescription>
      </CardHeader>

      <CardContent className='flex flex-wrap items-center gap-2'>
        {hasVerdict && (
          <Badge variant={VALUATION_BADGE_VARIANT[property.valuation_status]} className='rounded-sm'>
            {VALUATION_LABELS[property.valuation_status]}
          </Badge>
        )}
        {property.area !== null && (
          <Badge variant='outline' className='rounded-sm'>
            {property.area.toLocaleString("en-US")} متر
          </Badge>
        )}
        {property.rooms !== null && (
          <Badge variant='outline' className='rounded-sm'>
            {property.rooms} خواب
          </Badge>
        )}
      </CardContent>

      <CardFooter className='flex items-end justify-between gap-3'>
        <div className='flex flex-col'>
          <span className='text-base font-semibold tabular-nums'>
            {formatToman(property.total_price)}
          </span>
          <span className='text-muted-foreground text-xs tabular-nums'>
            {formatPricePerMeter(property.price_per_meter)}
          </span>
        </div>
        <div className='flex items-center gap-2'>
          <span
            className={cn(
              "text-sm font-medium tabular-nums",
              isBargain && "text-primary",
              property.valuation_status ==='OVERPRICED' && "text-destructive"
            )}
          >
            {formatDeviation(property.valuation_deviation_pct)}
          </span>
          <Button render={<Link href={`/dashboard/properties/${property.id}`} />} size='sm'>
            مشاهده
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
