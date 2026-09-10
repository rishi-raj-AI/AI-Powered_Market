import {ButtonHTMLAttributes, ReactNode} from 'react';

type Intent = 'primary' | 'secondary' | 'tertiary' | 'destructive';
type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  intent?: Intent;
  busy?: boolean;
  loadingLabel?: string;
  leadingIcon?: ReactNode;
};

export function Button({intent = 'primary', busy = false, loadingLabel = 'Working…', leadingIcon, children, disabled, className = '', ...props}: Props) {
  const intentClass = intent === 'secondary' ? 'secondary' : intent === 'tertiary' ? 'ghost' : intent === 'destructive' ? 'dangerBtn' : '';
  return <button {...props} className={`btn goButton ${intentClass} ${className}`.trim()} disabled={disabled || busy} aria-busy={busy || undefined}>{leadingIcon}<span>{busy ? loadingLabel : children}</span></button>;
}
