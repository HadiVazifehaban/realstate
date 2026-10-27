"use client";

import { FormEvent, useEffect, useRef } from 'react';
import type { Conversation, Message } from '../utils/types';
import { ChatHeader } from './chat-header';
import { MessageBubble } from './message-bubble';
import { MessageComposer } from './message-composer';
import { requestAuthJsSession } from '@/lib/auth/session';

type Props = {
  conversation: Conversation & { messages: Message[] };
  draft: string;
  sending: boolean;
  onDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function ChatArea({ conversation, draft, sending, onDraftChange, onSubmit }: Props) {
  const threadRef = useRef<HTMLDivElement>(null);
  const subjectRef = useRef('');
  useEffect(() => {
    let active = true;
    void requestAuthJsSession().then((session) => {
      if (active) subjectRef.current = session?.user?.id ?? '';
    });
    return () => { active = false; };
  }, []);
  useEffect(() => { threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight }); }, [conversation.messages]);
  return <section className='border-border/40 bg-background/80 flex min-h-0 flex-col gap-3 overflow-hidden rounded-2xl border p-4 lg:col-start-2'>
    <ChatHeader conversation={conversation} />
    <div ref={threadRef} className='min-h-0 flex-1 space-y-3 overflow-y-auto' aria-label='پیام‌های گفتگو'>
      {conversation.messages.map((message) => <MessageBubble key={message.id} message={message} own={message.senderSubject === subjectRef.current} />)}
      {conversation.messages.length === 0 && <p className='py-8 text-center text-sm text-muted-foreground'>هنوز پیامی در این گفتگو نیست.</p>}
    </div>
    <MessageComposer draft={draft} sending={sending} onDraftChange={onDraftChange} onSubmit={onSubmit} />
  </section>;
}