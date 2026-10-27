import type { Conversation } from '../utils/types';

export function ChatHeader({ conversation }: { conversation: Conversation }) {
  const names = conversation.members.map((member) => member.displayName).join('، ');
  return <header className='border-b pb-3'>
    <h2 className='font-semibold'>{conversation.title || names}</h2>
    <p className='text-xs text-muted-foreground'>{conversation.members.length} عضو · پیام‌رسان داخلی</p>
  </header>;
}