'use client';

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { IconPlus } from '@tabler/icons-react';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useAgencies, useCreateTransfer } from '@/features/network/hooks';

/** ثبت انتقال مسئولیت فایل به دفتر دیگر — با تأیید صریح. */
export function TransferCreateDialog({ agencyId }: { agencyId: string }) {
  const [open, setOpen] = React.useState(false);
  const [targetId, setTargetId] = React.useState('');
  const [propertyId, setPropertyId] = React.useState('');
  const [toUser, setToUser] = React.useState('');
  const [reason, setReason] = React.useState('');
  const [residual, setResidual] = React.useState(0);
  const [confirm, setConfirm] = React.useState(false);

  const queryClient = useQueryClient();
  const agencies = useAgencies();
  const create = useCreateTransfer();

  const partners = (agencies.data ?? []).filter((a) => a.id !== agencyId);
  const validUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(propertyId.trim());
  const canSubmit = targetId && validUuid && reason.trim().length >= 3 && confirm && !create.isPending;

  const submit = () => {
    if (!canSubmit) return;
    create.mutate(
      {
        property_id: propertyId.trim(),
        from_agency_id: agencyId,
        to_agency_id: targetId,
        to_user: toUser.trim() || undefined,
        reason: reason.trim(),
        residual_commission_pct: residual,
        confirm: true,
      },
      {
        onSuccess: () => {
          setOpen(false);
          setPropertyId('');
          setToUser('');
          setReason('');
          setResidual(0);
          setConfirm(false);
          void queryClient.invalidateQueries({ queryKey: ['network', 'transfers'] });
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <IconPlus className='ml-1 h-4 w-4' />
        ثبت انتقال فایل
      </DialogTrigger>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>انتقال مسئولیت فایل</DialogTitle>
          <DialogDescription>مسئولیت فایل به دفتر دیگر منتقل و در تاریخچه ثبت می‌شود.</DialogDescription>
        </DialogHeader>
        <div className='space-y-4'>
          <div className='space-y-2'>
            <Label>شناسه فایل (UUID)</Label>
            <Input value={propertyId} onChange={(e) => setPropertyId(e.target.value)} placeholder='xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' dir='ltr' />
          </div>
          <div className='space-y-2'>
            <Label>دفتر مقصد</Label>
            <Select value={targetId} onValueChange={(v) => setTargetId(v ?? '')}>
              <SelectTrigger><SelectValue placeholder='انتخاب دفتر…' /></SelectTrigger>
              <SelectContent>
                {partners.map((a) => (
                  <SelectItem key={a.id} value={a.id}>{a.name_fa || a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>مسئول جدید (اختیاری)</Label>
            <Input value={toUser} onChange={(e) => setToUser(e.target.value)} placeholder='نام کاربری مشاور مقصد' />
          </div>
          <div className='space-y-2'>
            <Label>دلیل انتقال</Label>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder='چرا مسئولیت منتقل می‌شود؟ (حداقل ۳ حرف)' />
          </div>
          <div className='space-y-2'>
            <Label>کارمزد باقی‌مانده دفتر قبل (٪)</Label>
            <Input type='number' min={0} max={100} value={residual} onChange={(e) => setResidual(Number(e.target.value))} />
          </div>
          <label className='flex items-center gap-2 text-sm'>
            <Checkbox checked={confirm} onCheckedChange={(v) => setConfirm(v === true)} />
            تأیید می‌کنم مسئولیت این فایل منتقل شود
          </label>
        </div>
        <DialogFooter>
          <Button variant='outline' onClick={() => setOpen(false)}>انصراف</Button>
          <Button onClick={submit} disabled={!canSubmit}>ثبت انتقال</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
