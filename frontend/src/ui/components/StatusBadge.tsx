import { AlertTriangle, CheckCircle2, Circle, Info, XCircle } from 'lucide-react';
import type { ReactNode } from 'react';

export type Tone = 'success' | 'warning' | 'error' | 'info' | 'neutral';

const TONES: Record<Tone, { classes: string; Icon: typeof Circle }> = {
  success: { classes: 'bg-success-soft text-success', Icon: CheckCircle2 },
  warning: { classes: 'bg-warning-soft text-warning', Icon: AlertTriangle },
  error: { classes: 'bg-error-soft text-error', Icon: XCircle },
  info: { classes: 'bg-info-soft text-info', Icon: Info },
  neutral: { classes: 'bg-muted text-fg-muted', Icon: Circle },
};

/** A status chip. Meaning is carried by icon and text, never by colour alone. */
export function StatusBadge({ tone, children }: { tone: Tone; children: ReactNode }) {
  const { classes, Icon } = TONES[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${classes}`}
    >
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      {children}
    </span>
  );
}
