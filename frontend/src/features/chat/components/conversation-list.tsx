"use client";

import { useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { Conversation } from '../utils/types';

type Props = { conversations: Conversation[]; selectedId: string; onSelect: (id: string) => void };

export function ConversationList({ conversations, selectedId, onSelect }: Props) {
  const [search, setSearch] = useState('');
  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return query ? conversations.filter((item) => item.title.toLocaleLowerCase().includes(query)) : conversations;
  }, [conversations, search]);
  return <aside className='border-border/40 bg-background/75 hidden h-full min-h-0 flex-col gap-4 overflow-hidden rounded-2xl border p-4 lg:flex'>
    <div><p className='font-semibold'>گفتگوها</p><p className='text-muted-foreground text-xs'>{conversations.length} گفتگو</p></div>
    <label className='sr-only' htmlFor='chat-search'>جست‌وجوی گفتگو</label>
    <Input id='chat-search' value={search} onChange={(event) => setSearch(event.target.value)} placeholder='جست‌وجو' />
    <div role='list' aria-label='فهرست گفتگوها' className='min-h-0 flex-1 space-y-2 overflow-y-auto'>
      {filtered.map((conversation) => <button key={conversation.id} type='button' role='listitem'
        aria-current={conversation.id === selectedId ? 'true' : undefined} onClick={() => onSelect(conversation.id)}
        className={cn('w-full rounded-xl border p-3 text-start', conversation.id === selectedId ? 'border-primary bg-primary/10' : 'border-transparent bg-background/70')}>
        <span className='block font-medium'>{conversation.title || conversation.members.map((member) => member.displayName).join('، ')}</span>
        <span className='mt-1 block truncate text-xs text-muted-foreground'>{conversation.lastMessage?.body ?? 'هنوز پیامی ثبت نشده است.'}</span>
      </button>)}
      {filtered.length === 0 && <p className='p-4 text-center text-sm text-muted-foreground'>گفتگویی پیدا نشد.</p>}
    </div>
  </aside>;
}