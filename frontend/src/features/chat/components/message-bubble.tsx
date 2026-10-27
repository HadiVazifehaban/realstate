import { cn } from '@/lib/utils';
import type { Message } from '../utils/types';

export function MessageBubble({ message, own }: { message: Message; own: boolean }) {
  const timestamp = new Intl.DateTimeFormat('fa-IR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(message.createdAt));
  return <article className={cn('max-w-[85%] rounded-2xl border px-4 py-3', own ? 'ms-auto bg-primary text-primary-foreground' : 'bg-muted')}>
    <p className='text-xs font-medium opacity-80'>{message.senderName}</p>
    <p className='mt-1 whitespace-pre-wrap break-words'>{message.body}</p>
    <time className='mt-2 block text-end text-[0.7rem] opacity-70' dateTime={message.createdAt}>{timestamp}</time>
  </article>;
}