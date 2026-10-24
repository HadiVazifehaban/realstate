"use client";

import * as React from 'react';
import { toast } from 'sonner';
import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { useQuota, useRevealContact } from '../hooks';
import type { Actor } from '../types';
import { maskPhone, toE164 } from '@/features/properties/utils/phone-mask';

/**
 * Owner-contact reveal, gated by the caller's daily plan quota.
 *
 * The number is never on the page before the reveal: the panel has no idea what
 * it is until the vault is opened, so a masked placeholder is drawn rather than
 * sample digits that would read as a real (wrong) number.
 *
 * A reveal is a deliberate, accountable act -- it spends one unit of the daily
 * quota and it is written to the audit log -- so it goes through a confirmation
 * dialog first. A single mis-click on a five-item lead list would otherwise cost
 * quota and leave an audit row the operator never meant to create.
 *
 * The revealed number is held in local component state only: it is never
 * written to the query cache or any storage, so a reload cannot replay it and
 * the plaintext exists only for as long as the operator is looking at it.
 */
export function RevealContactButton({
  propertyId,
  actor,
  reason ='تماس با مالک برای پیگیری لید'
}: {
  propertyId: string;
  actor?: Actor;
  reason?: string;
}) {
  const { data: quota } = useQuota(actor);
  const reveal = useRevealContact(actor);
  const [revealed, setRevealed] = React.useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  const remaining = quota?.remaining ?? null;
  const exhausted = remaining !== null && remaining <= 0;

  const confirmReveal = React.useCallback(async () => {
    try {
      const result = await reveal.mutateAsync({ propertyId, reason });
      if (result.owner_phone) {
        setRevealed(result.owner_phone);
        toast.success("شماره تماس رمزگشایی شد و در ممیزی ثبت گردید.");
      } else {
        toast.info("برای این فایل شماره تماسی ثبت نشده است.");
      }
    } finally {
      setConfirmOpen(false);
    }
  }, [reveal, propertyId, reason]);

  if (revealed) {
    return (
      <div className='flex items-center gap-2'>
        <a
          href={`tel:${toE164(revealed)}`}
          className='text-sm font-semibold tracking-widest tabular-nums'
          dir='ltr'
        >
          {revealed}
        </a>
        <Badge variant='outline' className='rounded-sm'>
          <Icons.lock />
          ثبت در ممیزی
        </Badge>
        <Button
          variant='ghost'
          size='icon-xs'
          onClick={() => setRevealed(null)}
          title='پنهان کردن'
        >
          <Icons.close />
        </Button>
      </div>
    );
  }

  return (
    <div className='flex items-center gap-2'>
      {/* A placeholder, not a hint: the panel has no idea what the number is
          until the vault is opened, and rendering sample digits would read as
          a real (wrong) phone number to the broker. */}
      <span
        className='text-muted-foreground font-mono text-sm tracking-widest'
        dir='ltr'
        title='شماره پس از نمایش، در لاگ ممیزی ثبت می‌شود'
      >
        •••• ••• ••••
      </span>
      <Button
        size='sm'
        variant='outline'
        disabled={exhausted || reveal.isPending}
        onClick={() => setConfirmOpen(true)}
      >
        {reveal.isPending ? <Icons.spinner className='animate-spin' /> : <Icons.eyeOff />}
        {exhausted ? "سهمیه تمام شد" : `نمایش شماره (${remaining ?? "∞"})`}
      </Button>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className='flex items-center gap-2'>
              <Icons.eye className='size-4' />
              نمایش شمارهٔ مالک
            </DialogTitle>
            <DialogDescription>
              شمارهٔ مالک رمزنگاری‌شده است و فقط با ثبت در ممیزی قابل مشاهده
              است. این کار یک واحد از سهمیهٔ روزانهٔ شما را مصرف می‌کند.
              {remaining !== null && (
                <span className='text-foreground mt-2 block text-xs font-medium'>
                  سهمیهٔ باقی‌مانده: {remaining} مورد
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant='ghost' onClick={() => setConfirmOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void confirmReveal()} disabled={reveal.isPending}>
              {reveal.isPending && <Icons.spinner className='animate-spin' />}
              نمایش و ثبت در ممیزی
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/**
 * A phone number already known to the page (a direct submission, the vault
 * export), rendered behind a reveal dialog.
 *
 * The mask keeps the operator's eye recognisable -- first six and last four
 * digits -- while the middle four stay hidden, so a screenshot of the page
 * cannot be dialled. The plaintext is only ever in the state of this component.
 */
export function MaskedPhone({
  value,
  onReveal,
  className
}: {
  value: string | null;
  onReveal?: () => void | Promise<void>;
  className?: string;
}) {
  const [revealed, setRevealed] = React.useState(false);

  if (!value) {
    return <span className={className}>—</span>;
  }

  if (revealed) {
    return (
      <span className={className}>
        <a
          href={`tel:${toE164(value)}`}
          className='tracking-widest tabular-nums'
          dir='ltr'
          onClick={() => setRevealed(false)}
        >
          {value}
        </a>
      </span>
    );
  }

  return (
    <span className={className}>
      <button
        type='button'
        className='text-muted-foreground hover:text-foreground tracking-widest tabular-nums transition-colors'
        dir='ltr'
        title='برای نمایش کامل کلیک کنید'
        onClick={() => {
          setRevealed(true);
          void onReveal?.();
        }}
      >
        {maskPhone(value)}
      </button>
    </span>
  );
}
