import { create } from 'zustand';
import { v4 as uuid } from 'uuid';
// import { persist } from 'zustand/middleware';

export type Priority = 'low' | 'medium' | 'high';

export type Task = {
  id: string;
  title: string;
  priority: Priority;
  description?: string;
  assignee?: string;
  dueDate?: string;
};

type KanbanState = {
  columns: Record<string, Task[]>;
  setColumns: (columns: Record<string, Task[]>) => void;
  addTask: (title: string, description?: string) => void;
};

/**
 * The desk's pipeline, in the order an Iranian real-estate office actually works
 * a file.
 *
 * New Lead -> First Contact -> Viewing -> Negotiation -> Contract -> Handed
 * Over, plus Lost for the files that die. Every advisor here reads a file in
 * this order, so the board is laid out the same way: a column that does not map
 * to a stage nobody can name is a column nobody drags cards into.
 *
 * The keys are English and stable because they are the persisted state; the
 * Persian labels live in ``board-column.tsx`` and are free to change.
 *
 * Seed data on purpose: Persian titles, Iranian names and real districts, so
 * the board a Maskanchi advisor opens on day one already shows the kind of card
 * they will file, rather than English demo tickets (Stripe, Okta, webhooks)
 * that make the page read as untranslated scaffolding.
 */
const initialColumns: Record<string, Task[]> = {
  newLead: [
    {
      id: '1',
      title: 'پیگیری تماس خریدار آپارتمان ۱۲۰ متری سعادت‌آباد',
      priority: 'high',
      assignee: 'سارا محمدی',
      dueDate: '2026-04-08',
      description: 'سرنخ از آگهی آنلاین؛ خریدار ودیعه ۵ میلیارد تا دارد.'
    },
    {
      id: '2',
      title: 'ثبت درخواست مالک ویلا ۳۵۰ متری لواسان',
      priority: 'medium',
      assignee: 'امیر رضایی',
      dueDate: '2026-04-09'
    },
    {
      id: '9',
      title: 'تماس با مالک واحد تجاری ملاصدرا',
      priority: 'medium',
      assignee: 'الناز کریمی',
      dueDate: '2026-04-10'
    }
  ],
  firstContact: [
    {
      id: '3',
      title: 'تماس اول: خریدارجوان برای متراژ ۸۰ تا ۹۵ متر',
      priority: 'high',
      assignee: 'سارا محمدی',
      dueDate: '2026-04-07',
      description: 'بودجه تا رهن ۴۰۰ میلیون؛ منطقهٔ ولنجک تا تجریش قبول است.'
    }
  ],
  viewing: [
    {
      id: '4',
      title: 'بازدید ملک: آپارتمان ۹۵ متری ونک — امروز ۱۷:۳۰',
      priority: 'high',
      assignee: 'امیر رضایی',
      dueDate: '2026-04-03'
    },
    {
      id: '5',
      title: 'هماهنگی بازدید ویلا باغستان با دو خریدار',
      priority: 'medium',
      assignee: 'الناز کریمی',
      dueDate: '2026-04-05'
    }
  ],
  negotiation: [
    {
      id: '6',
      title: 'مذاکرهٔ ودیعهٔ واحد ۸۵ متری پونک',
      priority: 'high',
      assignee: 'سارا محمدی',
      dueDate: '2026-04-04',
      description: 'مالک ۳۸۰ میلیون خواسته؛ خریدار پیشنهاد ۳۴۰ میلیارد داده — فاصلهٔ ۱۰٪.'
    }
  ],
  contract: [
    {
      id: '7',
      title: 'تنظیم قرارداد رهن و اجاره — دفتر مرکزی',
      priority: 'high',
      assignee: 'امیر رضایی',
      dueDate: '2026-04-02',
      description: 'عمر قرارداد دو ساله؛ چک تضمین جهت مالک تهیه شده.'
    }
  ],
  handedOver: [
    {
      id: '8',
      title: 'تحویلٔ کلید و تسویه — آپارتمان ۱۱۰ متری فرشته',
      priority: 'medium',
      assignee: 'الناز کریمی',
      dueDate: '2026-03-28'
    }
  ],
  lost: [
    {
      id: '10',
      title: 'انصراف خریدار — سقف بودجه کمتر از قیمت منطقه',
      priority: 'low',
      assignee: 'سارا محمدی',
      dueDate: '2026-03-30'
    }
  ]
};

export const useTaskStore = create<KanbanState>()(
  // To enable persistence across refreshes, uncomment the persist wrapper below:
  // persist(
  (set) => ({
    columns: initialColumns,

    setColumns: (columns) => set({ columns }),

    addTask: (title, description) =>
      set((state) => ({
        columns: {
          ...state.columns,
          newLead: [
            {
              id: uuid(),
              title,
              description,
              priority: 'medium' as Priority,
              assignee: undefined,
              dueDate: undefined
            },
            ...(state.columns.newLead ?? [])
          ]
        }
      }))
  })
  //   ,
  //   { name: 'kanban-store' }
  // )
);
