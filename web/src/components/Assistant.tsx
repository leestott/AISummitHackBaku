import { useRef, useState, type FormEvent } from "react";
import type { AssistantReply, Fact, Meta } from "../../../contracts/api";
import { api, errorMessage } from "../api";
import { copy } from "../i18n";
import { Icon } from "./Icon";
import { ErrorNotice, FactReferences, LoadingRows, Notice } from "./Shared";

export function Assistant({ meta, tripId, facts, today }: { meta: Meta | null; tripId?: string; facts: Fact[]; today: string }) {
  const [message, setMessage] = useState("");
  const [asked, setAsked] = useState("");
  const [reply, setReply] = useState<AssistantReply | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const offline = meta?.hosted_agents.configured === false;
  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || !message.trim()) return;
    lock.current = true; setPending(true); setError(null); setReply(null); setAsked(message.trim());
    try {
      setReply(await api.assistant(message.trim(), tripId));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      lock.current = false; setPending(false);
    }
  }
  return <section className="assistant-section" id="local-guide" aria-labelledby="assistant-title">
    <div className="assistant-intro"><div className="assistant-symbol"><Icon name="chat" /></div>
      <h2 id="assistant-title">{copy.assistant.heading}</h2><p>{copy.assistant.intro}</p>
      {meta?.hosted_agents.names.length ? <p className="agent-names">{meta.hosted_agents.names.join(" · ")}</p> : null}
    </div>
    <div className="assistant-interaction">
      {offline && <Notice>{copy.assistant.offline}</Notice>}
      <form onSubmit={ask}>
        <label htmlFor="assistant-message">{copy.assistant.label}</label>
        <textarea id="assistant-message" value={message} onChange={event => setMessage(event.target.value)} rows={3} maxLength={3000}
          placeholder={copy.assistant.placeholder} required disabled={pending || offline} />
        <button type="submit" className="button button-primary" disabled={pending || offline || !message.trim()}>
          {pending ? copy.assistant.pending : copy.assistant.ask}<Icon name="arrow" />
        </button>
      </form>
      <ErrorNotice message={error} />
      {pending && <LoadingRows label={copy.assistant.pending} />}
      {reply && <div className="assistant-answer" aria-live="polite">
        <p className="small-copy"><strong>{copy.assistant.question}: </strong>{asked}</p>
        <p className="answer-text">{reply.message}</p>
        <p className="agent-names">{copy.assistant.by}: {reply.agents.join(" · ")}</p>
        <p className="small-copy">{copy.assistant.notConfirmed}</p>
        {reply.fact_refs.length ? <><h3>{copy.assistant.grounded}</h3>
          <FactReferences ids={reply.fact_refs} facts={facts} today={today} /></> : <Notice>{copy.assistant.noRefs}</Notice>}
      </div>}
    </div>
  </section>;
}
