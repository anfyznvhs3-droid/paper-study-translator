import type { CSSProperties } from "react";

interface SummaryItem {
  label: string;
  value: number | string;
  unit?: string;
  textValue?: boolean;
}

/** Compact, non-interactive statistics shared by result, review and history. */
export function SummaryCards({label,items}:{label:string;items:SummaryItem[]}) {
  return <section className="summary-cards" aria-label={label} style={{"--summary-columns":Math.min(items.length,4)} as CSSProperties}>
    <dl>{items.map(item=><div className="summary-card" key={item.label}>
      <dt>{item.label}</dt>
      <dd className={item.textValue?"is-text-value":undefined}><span>{item.value}</span>{item.unit?<small>{item.unit}</small>:null}</dd>
    </div>)}</dl>
  </section>;
}
