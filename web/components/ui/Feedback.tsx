import {ReactNode} from 'react';
import {Button} from './Button';

type Tone = 'info' | 'success' | 'warning' | 'error';
export function Notice({tone = 'info', children}: {tone?: Tone; children: ReactNode}) { return <div className={`notice goNotice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{children}</div>; }
export function Loading({label = 'Loading…'}: {label?: string}) { return <div className="notice" role="status" aria-live="polite">{label}</div>; }
export function Empty({title, explanation, action}: {title: string; explanation: string; action?: ReactNode}) { return <section className="panel emptyState"><h3>{title}</h3><p className="muted">{explanation}</p>{action}</section>; }
export function Retry({message, onRetry, busy = false, retryLabel = 'Try again'}: {message: string; onRetry: () => void; busy?: boolean; retryLabel?: string}) { return <Notice tone="error"><p>{message}</p><Button intent="secondary" busy={busy} loadingLabel="Trying again…" onClick={onRetry}>{retryLabel}</Button></Notice>; }
