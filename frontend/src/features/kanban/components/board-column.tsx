"use client";

import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { KanbanColumn, KanbanColumnHandle } from '@/components/ui/kanban';
import type { Task } from '../utils/store';
import { TaskCard } from './task-card';

/**
 * Column labels, keyed by the store's column id.
 *
 * The keys stay English because they are persisted state: renaming a key would
 * orphan every stored task in that column. Only the displayed label is
 * translated. The seven stages are the desk's own pipeline -- a new lead is
 * worked through contact, viewing and negotiation to a signed contract and a
 * hand-over, and a file that dies lands in Lost rather than vanishing.
 */
const COLUMN_TITLES: Record<string, string> = {
  newLead: 'سرنخ جدید',
  firstContact: 'تماس اول',
  viewing: 'بازدید ملک',
  negotiation: 'مذاکره',
  contract: 'قرارداد',
  handedOver: 'تحویل شد',
  lost: 'از دست رفت'
};

interface TaskColumnProps extends Omit<React.ComponentProps<typeof KanbanColumn>, "children"> {
  tasks: Task[];
}

export function TaskColumn({ value, tasks, ...props }: TaskColumnProps) {
  return (
    <KanbanColumn value={value} className='w-full shrink-0 md:w-[320px]' {...props}>
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <span className='text-sm font-semibold'>{COLUMN_TITLES[value] ?? value}</span>
          <Badge variant='secondary' className='pointer-events-none rounded-sm'>
            {tasks.length}
          </Badge>
        </div>
        <KanbanColumnHandle render={<Button variant='ghost' size='icon' />}>
          <Icons.gripVertical className='h-4 w-4' />
        </KanbanColumnHandle>
      </div>
      <div className='flex flex-col gap-2 p-0.5'>
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} asHandle />
        ))}
      </div>
    </KanbanColumn>
  );
}
