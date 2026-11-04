import { Thread, ThreadGroup } from '../types.ts';

/**
 * Groups an array of threads (sorted desc by updated_at) into
 * { Today, Yesterday, Earlier } buckets. Pure function — no side effects.
 */
export function groupThreadsByDate(threads: Thread[]): ThreadGroup[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86_400_000;

  const today: Thread[] = [];
  const yesterday: Thread[] = [];
  const earlier: Thread[] = [];

  for (const t of threads) {
    const ts = new Date(t.updated_at).getTime();
    if (ts >= todayStart) {
      today.push(t);
    } else if (ts >= yesterdayStart) {
      yesterday.push(t);
    } else {
      earlier.push(t);
    }
  }

  const groups: ThreadGroup[] = [];
  if (today.length > 0) groups.push({ label: 'Today', threads: today });
  if (yesterday.length > 0) groups.push({ label: 'Yesterday', threads: yesterday });
  if (earlier.length > 0) groups.push({ label: 'Earlier', threads: earlier });
  return groups;
}
