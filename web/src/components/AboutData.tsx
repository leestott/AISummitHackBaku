import { useState } from "react";
import type { Fact } from "../../../contracts/api";
import { copy } from "../i18n";
import { formatDate, staleFact } from "../utils";
import { Icon } from "./Icon";
import { ErrorNotice, ExternalLink, LoadingRows, Notice } from "./Shared";

export function AboutData({ facts, today, error, loading, onRetry }: {
  facts: Fact[]; today: string; error: string | null; loading: boolean; onRetry: () => void;
}) {
  const [query, setQuery] = useState("");
  const visible = facts.filter(fact => `${fact.id} ${fact.topic} ${fact.statement}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="about-data page-width">
    <header className="page-intro"><h1 tabIndex={-1}>{copy.data.heading}</h1><p>{copy.data.lead}</p></header>
    <div className="data-principles">
      <section><Icon name="compass" /><h2>{copy.data.syntheticHeading}</h2><p>{copy.data.syntheticBody}</p></section>
      <section><Icon name="checklist" /><h2>{copy.data.sourcesHeading}</h2><p>{copy.data.sourcesBody}</p></section>
      <section><Icon name="shield" /><h2>{copy.data.privacyHeading}</h2><p>{copy.data.privacyBody}</p></section>
    </div>
    <section className="facts-section" aria-labelledby="facts-title">
      <div className="facts-heading"><h2 id="facts-title">{copy.data.factsHeading}</h2>
        <div className="field"><label htmlFor="facts-search">{copy.data.filter}</label>
          <input type="search" id="facts-search" value={query} onChange={event => setQuery(event.target.value)} placeholder={copy.data.placeholder} /></div>
      </div>
      <ErrorNotice message={error} onRetry={onRetry} />
      {loading && <LoadingRows />}
      {!loading && !facts.length && <Notice kind="warning">{copy.data.noFacts}</Notice>}
      <p className="small-copy" role="status">{copy.data.count(visible.length)}</p>
      <div className="facts-list">{visible.map(fact => <article key={fact.id} className="fact-record" id={`fact-${fact.id}`}>
        <div className="fact-title"><h3>{fact.topic}</h3><span className="source-id">{fact.id}</span>
          {(staleFact(fact, today) || fact.reverify_required) && <span className="stale-label"><Icon name="warning" />
            {staleFact(fact, today) ? copy.common.stale : copy.common.recheck}</span>}
        </div>
        <p>{fact.statement}</p>
        <div className="fact-provenance"><ExternalLink href={fact.source_url}>{copy.common.source}</ExternalLink>
          <span>{copy.common.checked(formatDate(fact.last_verified))}</span>
          <span>{copy.data.confidence}: {fact.confidence}</span>
        </div>
      </article>)}</div>
    </section>
  </div>;
}
