////////////////////////////////////////////////////////////////////////////////
// 🛑 Nothing in here has anything to do with Nextjs, it's just a fake database
//
// Roles and statuses mirror the backend's `UserRole` ladder (see
// features/users/constants/roles.ts) so the UI exercises the same vocabulary
// the API will eventually return.
// ////////////////////////////////////////////////////////////////////////////////

import { matchSorter } from 'match-sorter';
import { ROLE_VALUES, USER_STATUSES, type UserRole, type UserStatus } from '@/features/users/constants/roles';

export const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export type User = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  status: UserStatus;
  role: UserRole;
  created_at: string;
  updated_at: string;
};

// Persian given/family names so the RTL layout is exercised realistically.
const FIRST_NAMES = [
  'علی',
  'محمد',
  'رضا',
  'سمیه',
  'مریم',
  'حسین',
  'فاطمه',
  'امیر',
  'زهرا',
  'مهدی',
  'نگار',
  'سارا',
  'کاوه',
  'الهام',
  'بهروز',
  'شیما',
  'آرش',
  'پریسا',
  'کامران',
  'نیلوفر'
];

const LAST_NAMES = [
  'رضایی',
  'محمدی',
  'کریمی',
  'حسینی',
  'موسوی',
  'احمدی',
  'صادقی',
  'نوری',
  'قاسمی',
  'شریفی',
  'امینی',
  'زارعی',
  'دهقان',
  'کاظمی',
  'رحیمی',
  'یوسفی',
  'اکبری',
  'سلطانی',
  'طاهری',
  'فرهادی'
];

/**
 * Deterministic pseudo-random generator (mulberry32) so the demo dataset is
 * stable across reloads -- a table whose rows reshuffle on every render makes
 * pagination and filters look broken when they are not.
 */
function makeRng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const IRANIAN_MOBILE_PREFIXES = ['۹۱۲', '۹۳۳', '۹۳۵', '۹۹۱', '۹۹۳'];
const EMAIL_DOMAINS = ['amlak.ir', 'maskanchi.ir', 'sheypoor.ir'];

function generateRandomUserData(id: number, rng: () => number): User {
  const pick = <T,>(arr: readonly T[]): T => arr[Math.floor(rng() * arr.length)];

  const first = pick(FIRST_NAMES);
  const last = pick(LAST_NAMES);
  const mobile = pick(IRANIAN_MOBILE_PREFIXES);
  const suffix = String(1000000 + Math.floor(rng() * 8999999));
  const daysAgo = Math.floor(rng() * 900);

  return {
    id,
    first_name: first,
    last_name: last,
    email: `${first}${last}${id}@${pick(EMAIL_DOMAINS)}`,
    phone: `${mobile}${suffix}`,
    // Weighted toward ACTIVE, which is what a real office roster looks like.
    status: rng() < 0.75 ? 'ACTIVE' : 'INACTIVE',
    role: pick(ROLE_VALUES),
    created_at: new Date(Date.now() - daysAgo * 86_400_000).toISOString(),
    updated_at: new Date(Date.now() - Math.floor(rng() * 30) * 86_400_000).toISOString()
  };
}

// Mock user data store
export const fakeUsers = {
  records: [] as User[],

  initialize() {
    const rng = makeRng(20260904);
    const sampleUsers: User[] = [];
    for (let i = 1; i <= 50; i++) {
      sampleUsers.push(generateRandomUserData(i, rng));
    }

    this.records = sampleUsers;
  },

  async getAll({ roles = [], search }: { roles?: string[]; search?: string }) {
    let users = [...this.records];

    if (roles.length > 0) {
      users = users.filter((user) => roles.includes(user.role));
    }

    if (search) {
      users = matchSorter(users, search, {
        keys: ['first_name', 'last_name', 'email']
      });
    }

    return users;
  },

  async createUser(data: Omit<User, 'id' | 'created_at' | 'updated_at'>) {
    await delay(800);

    const newUser: User = {
      ...data,
      id: Math.max(0, ...this.records.map((r) => r.id)) + 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    this.records.push(newUser);

    return {
      success: true,
      message: 'کاربر جدید ایجاد شد',
      user: newUser
    };
  },

  async updateUser(id: number, data: Omit<User, 'id' | 'created_at' | 'updated_at'>) {
    await delay(800);

    const index = this.records.findIndex((user) => user.id === id);

    if (index === -1) {
      return { success: false, message: `کاربر با شناسه ${id} یافت نشد` };
    }

    this.records[index] = {
      ...this.records[index],
      ...data,
      updated_at: new Date().toISOString()
    };

    return {
      success: true,
      message: 'کاربر به‌روزرسانی شد',
      user: this.records[index]
    };
  },

  async deleteUser(id: number) {
    await delay(800);

    const index = this.records.findIndex((user) => user.id === id);

    if (index === -1) {
      return { success: false, message: `کاربر با شناسه ${id} یافت نشد` };
    }

    this.records.splice(index, 1);

    return {
      success: true,
      message: 'کاربر حذف شد'
    };
  },

  async getUsers({
    page = 1,
    limit = 10,
    roles,
    search,
    sort
  }: {
    page?: number;
    limit?: number;
    roles?: string | string[];
    search?: string;
    sort?: string;
  }) {
    await delay(800);
    const rolesArray = roles
      ? (Array.isArray(roles) ? roles : String(roles).split(/[.,]/)).filter((r): r is UserRole =>
          (ROLE_VALUES as string[]).includes(r)
        )
      : [];
    const allUsers = await this.getAll({
      roles: rolesArray,
      search
    });

    // Sorting
    if (sort) {
      try {
        const sortItems = JSON.parse(sort) as {
          id: string;
          desc: boolean;
        }[];
        if (sortItems.length > 0) {
          const { id, desc } = sortItems[0];
          allUsers.sort((a, b) => {
            // Handle computed 'name' column
            const aVal =
              id === 'name' ? `${a.first_name} ${a.last_name}` : (a as Record<string, unknown>)[id];
            const bVal =
              id === 'name' ? `${b.first_name} ${b.last_name}` : (b as Record<string, unknown>)[id];
            if (typeof aVal === 'number' && typeof bVal === 'number') {
              return desc ? bVal - aVal : aVal - bVal;
            }
            const aStr = String(aVal ?? '').toLowerCase();
            const bStr = String(bVal ?? '').toLowerCase();
            return desc ? bStr.localeCompare(aStr) : aStr.localeCompare(bStr);
          });
        }
      } catch {
        // Invalid sort param — ignore
      }
    }

    const totalUsers = allUsers.length;

    const offset = (page - 1) * limit;
    const paginatedUsers = allUsers.slice(offset, offset + limit);

    return {
      success: true,
      time: new Date().toISOString(),
      message: 'داده‌های نمونه برای تست و یادگیری',
      total_users: totalUsers,
      offset,
      limit,
      users: paginatedUsers,
      // Role histogram for the summary cards. Derived from the *filtered* set so
      // the counts agree with the rows on screen.
      role_breakdown: ROLE_VALUES.map((role) => ({
        role,
        count: allUsers.filter((u) => u.role === role).length
      }))
    };
  }
};

fakeUsers.initialize();
