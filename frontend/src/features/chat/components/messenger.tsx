"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { ChatApiError, fetchConversations, fetchMessages, sendMessage } from '../api/client';
import type { Conversation, Message } from '../utils/types';
import { ConversationList } from './conversation-list';
import { ConversationSelect } from './conversation-select';
import { ChatArea } from './chat-area';

export function Messenger() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Record<string, Message[]>>({});
  const [selectedId, setSelectedId] = useState('');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState('');

  const loadConversations = useCallback(async () => {
    setLoading(true);
    setError('');
    setErrorCode('');
    try {
      const rows = await fetchConversations();
      setConversations(rows);
      setSelectedId((current) => rows.some((row) => row.id === current) ? current : rows[0]?.id ?? '');
    } catch (cause) {
      setError(cause instanceof ChatApiError ? cause.message : 'گفتگوها بارگذاری نشدند.');
      setErrorCode(cause instanceof ChatApiError ? cause.code : '');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadConversations(); }, [loadConversations]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    fetchMessages(selectedId).then((rows) => {
      if (active) setMessages((current) => ({ ...current, [selectedId]: rows }));
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof ChatApiError ? cause.message : 'پیام‌ها بارگذاری نشدند.');
    });
    return () => { active = false; };
  }, [selectedId]);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === selectedId),
    [conversations, selectedId]
  );
  const activeMessages = messages[selectedId] ?? [];
  const mappedConversation = activeConversation
    ? { ...activeConversation, messages: activeMessages }
    : undefined;

  const submit = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body = draft.trim();
    if (!body || !selectedId || sending) return;
    setSending(true);
    setError('');
    try {
      const sent = await sendMessage(selectedId, body, uuidv4());
      setMessages((current) => ({
        ...current,
        [selectedId]: [...(current[selectedId] ?? []).filter((message) => message.id !== sent.id), sent]
      }));
      setDraft('');
      setConversations((current) => current.map((conversation) => conversation.id === selectedId
        ? { ...conversation, lastMessage: sent }
        : conversation));
    } catch (cause) {
      setError(cause instanceof ChatApiError ? cause.message : 'ارسال پیام ناموفق بود. متن را نگه داشتیم؛ دوباره تلاش کنید.');
    } finally {
      setSending(false);
    }
  }, [draft, selectedId, sending]);

  if (loading) return <div className='flex h-full items-center justify-center' role='status'>در حال بارگذاری گفتگوها…</div>;
  if (error && conversations.length === 0 && errorCode === 'workspace_membership_required') {
    return <div className='flex h-full flex-col items-center justify-center gap-3 p-6 text-center' role='status'>
      <p className='font-medium'>برای دسترسی به گفتگوی همکاران، عضویت فعال در یک دفتر لازم است.</p>
      <p className='text-sm text-muted-foreground'>از انتخاب‌گر دفتر، دفتر فعال را انتخاب کنید یا از مدیر دفتر بخواهید عضویت شما را تأیید کند.</p>
      <a className='text-primary underline' href='/dashboard/network/requests'>مدیریت همکاری دفترها</a>
    </div>;
  }
  if (error && conversations.length === 0) {
    return <div className='flex h-full flex-col items-center justify-center gap-3 text-center' role='alert'>
      <p>{error}</p><button type='button' className='text-primary underline' onClick={() => void loadConversations()}>تلاش دوباره</button>
    </div>;
  }
  if (conversations.length === 0) {
    return <div className='flex h-full items-center justify-center p-6 text-center text-muted-foreground'>
      هنوز گفتگویی برای شما در این دفتر وجود ندارد. ایجاد گفتگو تا زمان آماده‌شدن مدیریت اعضای دفتر غیرفعال است.
    </div>;
  }
  if (!mappedConversation) return null;

  return (
    <div className='border-border/50 bg-background/70 relative grid h-[calc(100dvh-5.5rem)] w-full grid-rows-[auto,1fr] gap-3 overflow-hidden rounded-2xl border p-3 backdrop-blur-xl sm:gap-4 sm:p-4 lg:[grid-template-columns:30%_1fr] lg:grid-rows-[1fr] lg:gap-4 lg:rounded-3xl lg:p-5'>
      {error && <p role='alert' className='absolute inset-x-4 top-2 z-10 rounded-lg bg-destructive/10 p-2 text-sm text-destructive'>{error}</p>}
      <ConversationSelect conversations={conversations} selectedId={selectedId} onSelect={setSelectedId} />
      <ConversationList conversations={conversations} selectedId={selectedId} onSelect={setSelectedId} />
      <ChatArea
        conversation={mappedConversation}
        draft={draft}
        sending={sending}
        onDraftChange={setDraft}
        onSubmit={submit}
      />
    </div>
  );
}