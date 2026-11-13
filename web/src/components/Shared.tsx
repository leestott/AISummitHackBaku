import type { ReactNode } from "react";
import type { Currency, ExchangeRates, Fact } from "../../../contracts/api";
import { copy } from "../i18n";
import { formatDate, money, safeUrl, staleFact } from "../utils";
import { Icon } from "./Icon";

export interface MoneyProps {
  currency: Currency;
  rates?: ExchangeRates;
}

export function Price({ amount, currency, rates, secondary = false }: MoneyProps & { amount: number; secondary?: boolean }) {
  return <span className="price">
    <span>{money(amount, currency, rates)}</span>
    {secondary && currency !== "AZN" && rates && <small>{money(amount, "AZN")}</small>}
  </span>;
}

export function Notice({ children, kind = "info", className = "" }: {
  children: ReactNode; kind?: "info" | "warning" | "success"; className?: string;
}) {
  return <div className={`notice notice-${kind} ${className}`}>
    <Icon name={kind === "warning" ? "warning" : kind === "success" ? "check" : "info"} />
    <div>{children}</div>
  </div>;
}

export function ErrorNotice({ message, onRetry }: { message: string | null; onRetry?: () => void }) {
  if (!message) return null;
  return <div className="notice notice-error" role="alert">
    <Icon name="warning" />
    <div><p>{message}</p>{onRetry && <button type="button" className="text-button" onClick={onRetry}>{copy.common.retry}</button>}</div>
  </div>;
}

export function ExternalLink({ href, children, className = "" }: { href: string; children: ReactNode; className?: string }) {
  const safe = safeUrl(href);
  return safe ? <a href={safe} target="_blank" rel="noopener noreferrer" className={`external-link ${className}`}>
    {children}<Icon name="external" />
  </a> : <span>{children}</span>;
}

export function FactReferences({ ids, facts, today, fallback }: {
  ids: string[]; facts: Fact[]; today: string;
  fallback?: { source_url: string; last_verified: string };
}) {
  const references = ids.map(id => facts.find(fact => fact.id === id)).filter((fact): fact is Fact => !!fact);
  if (!references.length && fallback) {
    return <div className="source-note">
      <ExternalLink href={fallback.source_url}>{copy.common.source}</ExternalLink>
      <span>{copy.common.checked(formatDate(fallback.last_verified))}</span>
    </div>;
  }
  if (!references.length) return <p className="source-note">{copy.common.noSources}</p>;
  return <div className="source-list">
    {references.map(fact => <div className="source-note" key={fact.id}>
      <ExternalLink href={fact.source_url}>{fact.topic} <span className="source-id">({fact.id})</span></ExternalLink>
      <span>{copy.common.checked(formatDate(fact.last_verified))}</span>
      {(staleFact(fact, today) || fact.reverify_required) && <span className="stale-label">
        <Icon name="warning" />{staleFact(fact, today) ? copy.common.stale : copy.common.recheck}
      </span>}
    </div>)}
  </div>;
}

export function SectionHeading({ title, children }: { title: string; children?: ReactNode }) {
  return <header className="section-heading"><h2>{title}</h2>{children && <p>{children}</p>}</header>;
}

export function LoadingRows({ label = copy.common.loading }: { label?: string }) {
  return <div className="loading-rows" role="status" aria-label={label}>
    <span className="sr-only">{label}</span><div /><div /><div />
  </div>;
}
