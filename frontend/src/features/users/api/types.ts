import type { UserRole, UserStatus } from '../constants/roles';

export type BackendUser = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  status: UserStatus;
  role: UserRole;
  created_at: string | null;
  updated_at: string | null;
};

export type { BackendUser as User };
export type { UserRole, UserStatus } from '../constants/roles';

export type UserFilters = {
  page?: number;
  limit?: number;
  roles?: string;
  search?: string;
  sort?: string;
};

export type RoleBreakdown = {
  role: UserRole;
  count: number;
};

export type UsersResponse = {
  success: boolean;
  time: string;
  message: string;
  total_users: number;
  offset: number;
  limit: number;
  users: BackendUser[];
  role_breakdown: RoleBreakdown[];
};

export type UserMutationPayload = {
  first_name: string;
  last_name: string;
  email?: string;
  phone: string;
  role: UserRole;
  status: UserStatus;
};
