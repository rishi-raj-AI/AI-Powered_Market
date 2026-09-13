import {InputHTMLAttributes} from 'react';

type Props = InputHTMLAttributes<HTMLInputElement> & {id: string; label: string; help?: string; errorMessage?: string; loadingMessage?: string; busy?: boolean};

export function FormField({id, label, help, errorMessage, loadingMessage, busy = false, 'aria-describedby': describedBy, 'aria-invalid': invalid, ...props}: Props) {
  const showLoading = busy && Boolean(loadingMessage);
  const descriptionId = errorMessage ? `${id}-error` : showLoading ? `${id}-loading` : help ? `${id}-help` : undefined;
  const descriptions = [describedBy, descriptionId].filter(Boolean).join(' ') || undefined;
  return <div className="field goField"><label htmlFor={id}>{label}</label><input {...props} id={id} aria-busy={busy || undefined} aria-invalid={errorMessage ? true : invalid} aria-describedby={descriptions}/>{errorMessage && <span id={`${id}-error`} className="error">{errorMessage}</span>}{!errorMessage && showLoading && <span id={`${id}-loading`} className="muted small" role="status">{loadingMessage}</span>}{!errorMessage && !showLoading && help && <span id={`${id}-help`} className="muted small">{help}</span>}</div>;
}
