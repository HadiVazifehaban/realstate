"use client";

import { FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

type Props = { draft: string; sending: boolean; onDraftChange: (value: string) => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void };

export function MessageComposer({ draft, sending, onDraftChange, onSubmit }: Props) {
  return <form onSubmit={onSubmit} className='flex items-end gap-3 border-t pt-3' aria-label='ارسال پیام'>
    <Textarea value={draft} onChange={(event) => onDraftChange(event.target.value)} maxLength={4000} rows={2}
      placeholder='پیام خود را بنویسید…' aria-label='متن پیام' required />
    <Button type='submit' disabled={sending || !draft.trim()}>{sending ? 'در حال ارسال…' : 'ارسال'}</Button>
  </form>;
}