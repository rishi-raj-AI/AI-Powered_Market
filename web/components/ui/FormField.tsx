import {InputHTMLAttributes} from 'react';

type Props = InputHTMLAttributes<HTMLInputElement> & {id: string; label: string; help?: string; errorMessage?: string; loadingMessage?: string; busy?: boolean};

export function FormField({id, label, help, errorMessage, loadingMessage, busy = false, ...props}: Props) {
  const descriptionId = errorMessage ? `${id}-error` : busy && loadingMessage ? `${id}-loading` : help ? `${id}-help` : undefined;
  return <div className="field goField"><label htmlFor={id}>{label}</label><input {...props} id={id} aria-invalid={errorMessage ? true : undefined} aria-describedby={descriptionId}/>{errorMessage && <span id={`${id}-error`} className="error">{errorMessage}</span>}{!errorMessage && busy && loadingMessage && <span id={`${id}-loading`} className="muted small" role="status">{loadingMessage}</span>}{!errorMessage && !busy && help && <span id={`${id}-help`} className="muted small">{help}</span>}</div>;
}
