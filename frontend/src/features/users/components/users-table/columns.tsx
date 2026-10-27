"use client";
import { Badge } from '@/components/ui/badge';
import { DataTableColumnHeader } from '@/components/ui/table/data-table-column-header';
import type { User } from '../../api/types';
import { Column, ColumnDef } from '@tanstack/react-table';
import { Icons } from '@/components/icons';
import { CellAction } from './cell-action';
import { ROLE_OPTIONS, STATUS_META, getRoleMeta } from '../../constants/roles';

export const columns: ColumnDef<User>[] = [
  {
    id: "name",
    accessorFn: (row) => `${row.first_name} ${row.last_name}`,
    header: ({ column }: { column: Column<User, unknown> }) => (
      <DataTableColumnHeader column={column} title='نام و نام خانوادگی' />
    ),
    cell: ({ row }) => (
      <div className='flex flex-col'>
        <span className='font-medium'>
          {row.original.first_name} {row.original.last_name}
        </span>
        <span className='text-muted-foreground text-xs'>{row.original.email}</span>
      </div>
    ),
    meta: {
      label: "نام",
      placeholder: "جستجوی کاربر...",
      variant: "text" as const,
      icon: Icons.text
    },
    enableColumnFilter: true
  },
  {
    accessorKey: "phone",
    header: "شماره تماس"
  },
  {
    id: "role",
    accessorKey: "role",
    enableSorting: false,
    header: ({ column }: { column: Column<User, unknown> }) => (
      <DataTableColumnHeader column={column} title='نقش' />
    ),
    cell: ({ cell }) => {
      const meta = getRoleMeta(cell.getValue<User["role"]>());
      return (
        <Badge variant={meta.badgeVariant} title={meta.description}>
          {meta.label}
        </Badge>
      );
    },
    enableColumnFilter: true,
    meta: {
      label: "نقش‌ها",
      variant: "multiSelect" as const,
      options: ROLE_OPTIONS
    }
  },
  {
    id: "realm_roles",
    accessorFn: (row) => row.realm_roles?.join(', ') ?? '',
    header: 'نقش‌های Keycloak',
    cell: ({ row }) => (
      <div className='flex max-w-[260px] flex-wrap gap-1'>
        {(row.original.realm_roles ?? []).length > 0 ? (
          row.original.realm_roles?.map((role) => (
            <Badge key={role} variant={role === 'ROLE_ADMIN' ? 'default' : 'outline'} className='text-[10px]'>
              {role.replace(/^ROLE_/, '')}
            </Badge>
          ))
        ) : (
          <span className='text-xs text-muted-foreground'>بدون نقش Realm</span>
        )}
      </div>
    ),
    enableSorting: false
  },
  {
    id: "verification",
    header: 'احراز هویت',
    cell: ({ row }) => (
      <div className='flex min-w-[120px] flex-col gap-1 text-xs'>
        <span className={row.original.kyc_status === 'VERIFIED' ? 'text-emerald-600' : 'text-muted-foreground'}>
          KYC: {row.original.kyc_status ?? 'PENDING'}
        </span>
        <span className={row.original.mobile_verified ? 'text-emerald-600' : 'text-muted-foreground'}>
          موبایل: {row.original.mobile_verified ? 'تأییدشده' : 'تأییدنشده'}
        </span>
      </div>
    ),
    enableSorting: false
  },
  {
    accessorKey: "status",
    header: "وضعیت",
    cell: ({ cell }) => {
      const raw = cell.getValue<User["status"]>();
      const meta = STATUS_META[raw];
      if (!meta) return <Badge variant='outline'>{String(raw)}</Badge>;
      return <Badge variant={meta.badgeVariant}>{meta.label}</Badge>;
    }
  },
  {
    id: "actions",
    cell: ({ row }) => <CellAction data={row.original} />
  }
];
