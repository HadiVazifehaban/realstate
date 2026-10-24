"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { FieldGroup } from '@/components/ui/field';
import { useAppForm } from '@/lib/form';
import { LoadingButton } from '@/components/ui/loading-button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet';
import { Icons } from '@/components/icons';
import { useMutation } from '@tanstack/react-query';
import { getQueryClient } from '@/lib/query-client';
import { createUserMutation, updateUserMutation } from '../api/mutations';
import { userKeys } from '../api/queries';
import type { User } from '../api/types';
import { toast } from 'sonner';
import { userSchema, type UserFormValues, normalizePhone, normalizeEmail } from '../schemas/user';
import { ROLE_OPTIONS, STATUS_OPTIONS, ROLES } from '../constants/roles';

const ROLE_DESCRIPTIONS = new Map(ROLES.map((r) => [r.value, r.description]));

interface UserFormSheetProps {
  user?: User;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UserFormSheet({ user, open, onOpenChange }: UserFormSheetProps) {
  const isEdit = !!user;

  const createMutation = useMutation({
    ...createUserMutation,
    onSuccess: (data, variables, onMutateResult, context) => {
      // The shared mutation's onSuccess only invalidates a *module-level*
      // client; refresh the app's real client so the visible table updates.
      getQueryClient().invalidateQueries({ queryKey: userKeys.all });
      createUserMutation.onSuccess?.(data, variables, onMutateResult, context);
      toast.success("کاربر ایجاد شد");
      onOpenChange(false);
      form.reset();
    },
    onError: (error) => toast.error(error.message || "ایجاد کاربر ناموفق بود. دوباره تلاش کنید.")
  });

  const updateMutation = useMutation({
    ...updateUserMutation,
    onSuccess: (data, variables, onMutateResult, context) => {
      getQueryClient().invalidateQueries({ queryKey: userKeys.all });
      updateUserMutation.onSuccess?.(data, variables, onMutateResult, context);
      toast.success("کاربر به‌روزرسانی شد");
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error(error.message || "به‌روزرسانی کاربر ناموفق بود. دوباره تلاش کنید.")
  });

  const form = useAppForm({
    defaultValues: {
      first_name: user?.first_name ?? "",
      last_name: user?.last_name ?? "",
      email: user?.email ?? "",
      phone: user?.phone ?? "",
      role: user?.role ?? "AGENT",
      status: user?.status ?? "ACTIVE"
    } as UserFormValues,
    validators: {
      onSubmit: userSchema
    },
    // TanStack silently swallows failed validation — without this, a
    // mis-filled field makes the button look dead.
    onSubmitInvalid: ({ formApi }) => {
      const fieldMeta = formApi.state.fieldMeta;
      // fieldMeta is keyed by the form's own field names; Object.keys widens
      // them to string, so re-narrow before indexing or TS rejects the lookup.
      for (const key of Object.keys(fieldMeta) as (keyof typeof fieldMeta)[]) {
        const meta = fieldMeta[key]?.errors?.[0];
        if (meta) {
          const msg = typeof meta ==='string' ? meta : "خطا در فرم";
          toast.error("لطفاً خطاهای فرم را اصلاح کنید", { description: msg });
          break;
        }
      }
      formApi.validate("submit");
    },
    onSubmit: async ({ value }) => {
      // Normalise before leaving: the user may type Persian digits
      // (۰۹۱۲…) — the DB must store the canonical Latin form.
      const payload = {
        ...value,
        phone: normalizePhone(value.phone),
        email: normalizeEmail(value.email) ?? ""
      };
      if (isEdit) {
        await updateMutation.mutateAsync({ id: user.id, values: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
    }
  });

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className='flex flex-col'>
        <SheetHeader>
          <SheetTitle>{isEdit ? "ویرایش کاربر" : "کاربر جدید"}</SheetTitle>
          <SheetDescription>
            {isEdit
              ? "اطلاعات کاربر را ویرایش کنید."
              : "برای ایجاد کاربر جدید، اطلاعات را وارد کنید."}
          </SheetDescription>
        </SheetHeader>

        <div className='flex-1 overflow-auto'>
          <form
            id='user-form-sheet'
            className='space-y-4 p-4 md:p-4'
            onSubmit={(e) => {
              e.preventDefault();
              form.handleSubmit();
            }}
          >
            <FieldGroup>
              <div className='grid grid-cols-2 gap-4'>
                <form.AppField
                  name='first_name'
                  children={(field) => <field.TextField label='نام' required placeholder='علی' />}
                />
                <form.AppField
                  name='last_name'
                  children={(field) => (
                    <field.TextField label='نام خانوادگی' required placeholder='رضایی' />
                  )}
                />
              </div>

              <form.AppField
                name='email'
                children={(field) => (
                  <field.TextField
                    label='ایمیل'
                    required
                    type='email'
                    placeholder='name@example.com'
                  />
                )}
              />

              <form.AppField
                name='phone'
                children={(field) => (
                  <field.TextField
                    label='شماره تماس'
                    required
                    type='tel'
                    placeholder='۰۹۱۲۱۲۳۴۵۶۷'
                  />
                )}
              />

              <form.AppField
                name='role'
                children={(field) => (
                  <field.SelectField
                    label='نقش'
                    required
                    options={ROLE_OPTIONS}
                    placeholder='انتخاب نقش'
                    // Explains what the selected tier can actually do, since the
                    // role ladder is what gates PII, lead closing and data edits.
                    description={ROLE_DESCRIPTIONS.get(field.state.value as never)}
                  />
                )}
              />

              <form.AppField
                name='status'
                children={(field) => (
                  <field.SelectField
                    label='وضعیت'
                    required
                    options={STATUS_OPTIONS}
                    placeholder='انتخاب وضعیت'
                  />
                )}
              />
            </FieldGroup>
          </form>
        </div>

        <SheetFooter>
          <Button type='button' variant='outline' onClick={() => onOpenChange(false)}>
            انصراف
          </Button>
          <LoadingButton loading={isPending} type='submit' form='user-form-sheet'>
            {isEdit ? "ذخیره تغییرات" : "ایجاد کاربر"}
          </LoadingButton>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export function UserFormSheetTrigger() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Icons.add className='me-2 h-4 w-4' /> افزودن کاربر
      </Button>
      <UserFormSheet open={open} onOpenChange={setOpen} />
    </>
  );
}
