"use client";

import type { Conversation } from '../utils/types';

type Props = { conversations: Conversation[]; selectedId: string; onSelect: (id: string) => void };

export function ConversationSelect({ conversations, selectedId, onSelect }: Props) {
  return <label className='lg:hidden'>
    <span className='sr-only'>انتخاب گفتگو</span>
    <select className='w-full rounded-xl border bg-background p-3' value={selectedId} onChange={(event) => onSelect(event.target.value)}>
      {conversations.map((conversation) => <option key={conversation.id} value={conversation.id}>
        {conversation.title || conversation.members.map((member) => member.displayName).join('، ')}
      </option>)}
    </select>
  </label>;
}