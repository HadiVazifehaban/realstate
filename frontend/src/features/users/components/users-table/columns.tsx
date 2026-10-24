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
