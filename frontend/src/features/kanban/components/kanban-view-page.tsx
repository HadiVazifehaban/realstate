import PageContainer from '@/components/layout/page-container';
import { KanbanBoard } from './kanban-board';
import NewTaskDialog from './new-task-dialog';

export default function KanbanViewPage() {
  return (
    <PageContainer
      pageTitle='تخته کارها'
      pageDescription='مدیریت وظایف با کشیدن و رها کردن'
      pageHeaderAction={<NewTaskDialog />}
    >
      <KanbanBoard />
    </PageContainer>
  );
}
