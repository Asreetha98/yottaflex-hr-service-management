type Tone = 'gray' | 'blue' | 'green' | 'amber' | 'red' | 'purple';

const tones: Record<Tone, string> = {
  gray: 'bg-slate-100 text-slate-700',
  blue: 'bg-blue-100 text-blue-800',
  green: 'bg-emerald-100 text-emerald-800',
  amber: 'bg-amber-100 text-amber-800',
  red: 'bg-red-100 text-red-800',
  purple: 'bg-purple-100 text-purple-800',
};

const statusTone: Record<string, Tone> = {
  NEW: 'gray',
  CLASSIFIED: 'blue',
  AWAITING_CLARIFICATION: 'amber',
  ASSIGNED: 'blue',
  IN_PROGRESS: 'blue',
  ESCALATED: 'red',
  RESOLVED: 'green',
  CLOSED: 'gray',
  REOPENED: 'amber',
  CANCELLED: 'gray',
  P1: 'red',
  P2: 'amber',
  P3: 'gray',
  ACTIVE: 'blue',
  PAUSED: 'amber',
  MET: 'green',
  BREACHED: 'red',
  PUBLISHED: 'green',
  DRAFT: 'amber',
  ARCHIVED: 'gray',
};

interface Props {
  label: string;
  tone?: Tone;
}

/** Badge whose colour is derived from the label when no tone is given. */
export default function Badge({ label, tone }: Props) {
  const resolved = tone ?? statusTone[label] ?? 'gray';
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${tones[resolved]}`}>
      {label.replace(/_/g, ' ')}
    </span>
  );
}
