type Props = {subtotal: string | number; deliveryFee: string | number; total: string | number; format: (value: string | number) => string; sourceStatus?: 'quote' | 'confirmed'; blockers?: string[]; labels?: {subtotal: string; deliveryFee: string; total: string}};

export function PriceBreakdown({subtotal, deliveryFee, total, format, sourceStatus = 'quote', blockers = [], labels = {subtotal: 'Subtotal', deliveryFee: 'Local delivery', total: 'Total'}}: Props) {
  return <section aria-label={sourceStatus === 'confirmed' ? 'Confirmed order total' : 'Current order quote'}><div className="metricRow"><span>{labels.subtotal}</span><strong>{format(subtotal)}</strong></div><div className="metricRow"><span>{labels.deliveryFee}</span><strong>{format(deliveryFee)}</strong></div><div className="metricRow totalRow"><span>{labels.total}</span><strong>{format(total)}</strong></div>{blockers.map(blocker => <div className="notice dangerText small" key={blocker}>{blocker}</div>)}</section>;
}
