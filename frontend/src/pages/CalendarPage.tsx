import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { Paginated, Task } from '../lib/types';

export default function CalendarPage() {
  const { data } = useQuery({
    queryKey: ['tasks-all'],
    queryFn: async () => (await api.get<Paginated<Task> | Task[]>('/tasks/?ordering=due_date')).data,
  });
  const rows = Array.isArray(data) ? data : (data?.results ?? []);
  return (
    <div>
      <h1>Plans & calendar</h1>
      <table>
        <thead><tr><th>Due</th><th>Task</th><th>Campaign</th><th>Done</th></tr></thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}><td>{t.due_date ?? '—'}</td><td>{t.title}</td><td>{t.campaign ?? '—'}</td><td>{t.done ? 'yes' : 'no'}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
