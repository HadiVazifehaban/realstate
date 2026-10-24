'use client';

import { useState } from 'react';
import { useRealmRoles } from '@/hooks/use-auth';
import { useAuthUser } from '@/hooks/use-auth';
import { useAuthContext } from '@/hooks/use-auth';
import PageContainer from '@/components/layout/page-container';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Icons } from '@/components/icons';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface KeycloakUser {
  id: string;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  enabled: boolean;
  attributes?: {
    kyc_status?: string[];
  };
  realmRoles?: string[];
}

const ALL_ROLES = [
  { name: 'ROLE_OWNER', label: 'شخص حقیقی' },
  { name: 'ROLE_SENIOR_BROKER', label: 'مشاور ارشد' },
  { name: 'ROLE_JUNIOR_BROKER', label: 'مشاور جونیور' },
  { name: 'ROLE_AGENCY_MANAGER', label: 'مدیر دفتر' },
  { name: 'ROLE_SUPERVISOR', label: 'سرپرست' },
  { name: 'ROLE_ADMIN', label: 'مدیر سامانه' },
  { name: 'ROLE_VERIFIED_USER', label: 'کاربر تایید شده' },
  { name: 'ROLE_DATA_ANALYST', label: 'تحلیل‌گر داده' },
];

export default function RolesPage() {
  const roles = useRealmRoles();
  const user = useAuthUser();
  const { kycStatus, isApproved } = useAuthContext();
  const [users, setUsers] = useState<KeycloakUser[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await fetch('/backend/api/v1/admin/users', {
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users || []);
      } else {
        console.error('Failed to fetch users:', response.status, response.statusText);
        const errorText = await response.text();
        console.error('Error response:', errorText);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setLoading(false);
    }
  };

  const approveUser = async (userId: string) => {
    try {
      const response = await fetch('/backend/api/v1/admin/users/approve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ userId }),
      });
      if (response.ok) {
        await fetchUsers();
      } else {
        const errorText = await response.text();
        console.error('Failed to approve user:', response.status, errorText);
        alert(`خطا در تایید کاربر: ${response.status} - ${errorText}`);
      }
    } catch (error) {
      console.error('Failed to approve user:', error);
      alert(`خطا در ارتباط با سرور: ${error}`);
    }
  };

  const setUserRole = async (userId: string, roleName: string) => {
    try {
      const response = await fetch('/backend/api/v1/admin/users/role', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ userId, roleName }),
      });
      if (response.ok) {
        await fetchUsers();
      } else {
        const errorText = await response.text();
        console.error('Failed to set user role:', response.status, errorText);
        alert(`خطا در تغییر نقش: ${response.status} - ${errorText}`);
      }
    } catch (error) {
      console.error('Failed to set user role:', error);
      alert(`خطا در ارتباط با سرور: ${error}`);
    }
  };

  const getKycStatus = (user: KeycloakUser) => {
    // Since Keycloak attributes don't work, use ROLE_OWNER as a proxy for approval
    const hasOwnerRole = user.realmRoles?.includes('ROLE_OWNER');
    return hasOwnerRole ? 'VERIFIED' : 'PENDING';
  };

  const getRoleDisplayName = (role: string) => {
    const roleMap: Record<string, string> = {
      'ROLE_OWNER': 'شخص حقیقی',
      'ROLE_SENIOR_BROKER': 'مشاور ارشد',
      'ROLE_JUNIOR_BROKER': 'مشاور جونیور',
      'ROLE_AGENCY_MANAGER': 'مدیر دفتر',
      'ROLE_SUPERVISOR': 'سرپرست',
      'ROLE_ADMIN': 'مدیر سامانه',
      'ROLE_VERIFIED_USER': 'کاربر تایید شده',
      'ROLE_DATA_ANALYST': 'تحلیل‌گر داده',
    };
    return roleMap[role] || role;
  };

  return (
    <PageContainer
      pageTitle='مدیریت کاربران و نقش‌ها'
      pageDescription='تایید کاربران و مدیریت نقش‌های Keycloak'
    >
      <div className='space-y-6'>
        {/* Current User Info */}
        <Card>
          <CardHeader>
            <CardTitle>اطلاعات کاربر فعلی</CardTitle>
            <CardDescription>نقش‌ها و وضعیت احراز هویت شما</CardDescription>
          </CardHeader>
          <CardContent>
            <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
              <div className='space-y-1'>
                <p className='text-sm text-muted-foreground'>نام</p>
                <p className='font-medium'>{user?.fullName || 'نامشخص'}</p>
              </div>
              <div className='space-y-1'>
                <p className='text-sm text-muted-foreground'>ایمیل</p>
                <p className='font-medium'>{user?.emailAddresses[0]?.emailAddress || 'نامشخص'}</p>
              </div>
              <div className='space-y-1'>
                <p className='text-sm text-muted-foreground'>وضعیت KYC</p>
                <Badge variant={isApproved ? 'default' : 'secondary'}>
                  {kycStatus}
                </Badge>
              </div>
              <div className='space-y-1'>
                <p className='text-sm text-muted-foreground'>تایید شده</p>
                <Badge variant={isApproved ? 'default' : 'destructive'}>
                  {isApproved ? 'بله' : 'خیر'}
                </Badge>
              </div>
            </div>
            <div className='mt-4 space-y-2'>
              <p className='text-sm text-muted-foreground'>نقش‌ها</p>
              <div className='flex flex-wrap gap-2'>
                {roles.length === 0 ? (
                  <p className='text-muted-foreground text-sm'>هیچ نقشی ندارید</p>
                ) : (
                  roles.map((role) => (
                    <Badge key={role} variant='outline'>
                      {getRoleDisplayName(role)}
                    </Badge>
                  ))
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* User Management */}
        <Card>
          <CardHeader>
            <div className='flex items-center justify-between'>
              <div>
                <CardTitle>مدیریت کاربران</CardTitle>
                <CardDescription>لیست کاربران Keycloak و امکان تایید</CardDescription>
              </div>
              <Button onClick={fetchUsers} disabled={loading} size='lg'>
                <Icons.refresh className={loading ? 'animate-spin' : 'mr-2'} />
                {loading ? 'در حال بارگذاری...' : 'بارگذاری کاربران'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {users.length === 0 && !loading ? (
              <div className='text-center py-12'>
                <Icons.user className='mx-auto h-12 w-12 text-muted-foreground mb-4' />
                <p className='text-muted-foreground'>هنوز کاربری بارگذاری نشده است.</p>
                <p className='text-sm text-muted-foreground mt-2'>روی دکمه "بارگذاری کاربران" کلیک کنید.</p>
              </div>
            ) : (
              <div className='rounded-md border'>
                <Table dir='rtl'>
                  <TableHeader>
                    <TableRow>
                      <TableHead className='text-right'>کاربر</TableHead>
                      <TableHead className='text-right'>ایمیل</TableHead>
                      <TableHead className='text-right'>وضعیت KYC</TableHead>
                      <TableHead className='text-right'>نقش‌ها</TableHead>
                      <TableHead className='text-left'>عملیات</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell>
                          <div className='flex items-center gap-3'>
                            <div className='h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center'>
                              <Icons.user className='h-5 w-5 text-primary' />
                            </div>
                            <div className='text-right'>
                              <p className='font-medium'>{u.firstName} {u.lastName}</p>
                              <p className='text-sm text-muted-foreground'>@{u.username}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <p className='text-sm text-right'>{u.email}</p>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getKycStatus(u) === 'VERIFIED' ? 'default' : 'secondary'}>
                            {getKycStatus(u)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className='flex flex-wrap gap-1 justify-start'>
                            {u.realmRoles?.map((role) => (
                              <Badge key={role} variant='outline' className='text-xs'>
                                {getRoleDisplayName(role)}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className='text-left'>
                          <div className='flex gap-2 justify-start'>
                            {getKycStatus(u) !== 'VERIFIED' && (
                              <Button
                                size='sm'
                                onClick={() => approveUser(u.id)}
                                title='تایید کاربر'
                              >
                                <Icons.check className='h-4 w-4' />
                              </Button>
                            )}
                            <DropdownMenu>
                              <DropdownMenuTrigger>
                                <Button size='sm' variant='outline'>
                                  <Icons.settings className='h-4 w-4' />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align='end'>
                                {ALL_ROLES.map((role) => (
                                  <DropdownMenuItem
                                    key={role.name}
                                    onClick={() => setUserRole(u.id, role.name)}
                                  >
                                    {role.label}
                                  </DropdownMenuItem>
                                ))}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
