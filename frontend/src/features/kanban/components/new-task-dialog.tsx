"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useTaskStore } from '../utils/store';

export default function NewTaskDialog() {
  const addTask = useTaskStore((state) => state.addTask);
  const [open, setOpen] = useState(false);
  const [titleError, setTitleError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const form = e.currentTarget;
    if (!form.reportValidity()) return;
    const formData = new FormData(form);
    const { title, description } = Object.fromEntries(formData);

    if (typeof title !=='string' || typeof description !=='string') return;
    if (!title.trim()) {
      setTitleError("عنوان کار را وارد کنید.");
      return;
    }
    setTitleError(null);
    addTask(title, description);
    form.reset();
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setTitleError(null);
      }}
    >
      <DialogTrigger render={<Button variant='secondary' size='sm' />}>
        + افزودن کار جدید
      </DialogTrigger>
      <DialogContent className='sm:max-w-[425px]'>
        <DialogHeader>
          <DialogTitle>افزودن کار جدید</DialogTitle>
          <DialogDescription>امروز می‌خواهید چه کاری انجام شود؟</DialogDescription>
        </DialogHeader>
        <form id='task-form' className='grid gap-4 py-4' onSubmit={handleSubmit}>
          <div className='grid grid-cols-4 items-center gap-4'>
            <Input
              id='title'
              name='title'
              placeholder='عنوان کار…'
              aria-label='عنوان کار'
              required
              aria-invalid={!!titleError}
              aria-describedby={titleError ? "task-title-error" : undefined}
              className='col-span-4'
            />
            {titleError && (
              <p id='task-title-error' role='alert' className='text-destructive col-span-4 text-sm'>
                {titleError}
              </p>
            )}
          </div>
          <div className='grid grid-cols-4 items-center gap-4'>
            <Textarea
              id='description'
              name='description'
              placeholder='توضیحات…'
              aria-label='توضیحات کار'
              className='col-span-4'
            />
          </div>
        </form>
        <DialogFooter>
          <Button type='submit' size='sm' form='task-form'>
            افزودن کار
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
