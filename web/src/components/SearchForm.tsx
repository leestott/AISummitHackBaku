import { useRef, useState, type FormEvent } from "react";
import type { Meta, ParsedSearch, SearchParams } from "../../../contracts/api";
import { api, errorMessage } from "../api";
import { copy } from "../i18n";
import { exampleSearch, interestIds, regionIds } from "../utils";
import { Icon } from "./Icon";
import { ErrorNotice, Notice } from "./Shared";

interface Props {
  meta: Meta | null;
  initial?: SearchParams;
  busy: boolean;
  error: string | null;
  locked: boolean;
  onSearch: (params: SearchParams) => Promise<boolean>;
}

export function SearchForm({ meta, initial, busy, error, locked, onSearch }: Props) {
  const [params, setParams] = useState<SearchParams>(() => initial ?? exampleSearch(meta?.today));
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<ParsedSearch | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const parseLock = useRef(false);
  const parsedHeading = useRef<HTMLHeadingElement>(null);
  const disabled = busy || parsing || locked;
  const set = <K extends keyof SearchParams>(key: K, value: SearchParams[K]) => {
    setParams(current => ({ ...current, [key]: value }));
    setValidation(null);
  };
  const toggle = (key: "interests" | "regions", value: string) => {
    set(key, params[key].includes(value) ? params[key].filter(item => item !== value) : [...params[key], value]);
  };

  async function parse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (parseLock.current || !text.trim()) return;
    parseLock.current = true;
    setParsing(true);
    setParseError(null);
    try {
      const response = await api.parseSearch(text.trim());
      setParams(response.search_params);
      setParsed(response);
      setValidation(null);
      window.setTimeout(() => parsedHeading.current?.focus(), 0);
    } catch (cause) {
      setParseError(errorMessage(cause));
    } finally {
      parseLock.current = false;
      setParsing(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled) return;
    if (!params.origin.trim()) return setValidation(copy.search.originError);
    if (!params.arrival || !params.departure || params.departure <= params.arrival) return setValidation(copy.search.dateError);
    if (!Number.isInteger(params.adults) || params.adults < 1 || params.adults > 12 ||
      !Number.isInteger(params.children) || params.children < 0 || params.children > 11 ||
      params.adults + params.children > 12) {
      return setValidation(copy.search.partyError);
    }
    if (!params.interests.length) return setValidation(copy.search.interestsError);
    setValidation(null);
    await onSearch({ ...params, origin: params.origin.trim() });
  }

  return <section className="search-section" id="plan-a-trip" aria-labelledby="search-title">
    <header className="search-heading">
      <div><h2 id="search-title">{copy.hero.searchTitle}</h2><p>{copy.hero.searchDescription}</p></div>
      <button type="button" className="text-button example-button" disabled={disabled} onClick={() => {
        setParams(exampleSearch(meta?.today)); setParsed(null); setValidation(null);
      }}><Icon name="compass" />{copy.search.example}</button>
    </header>
    <details className="natural-search">
      <summary><Icon name="chat" />{copy.search.natural}</summary>
      <p>{copy.search.parseNote}</p>
      {meta?.hosted_agents.configured === false && <Notice>{copy.search.agentOffline}</Notice>}
      <form onSubmit={parse}>
        <label htmlFor="trip-description">{copy.search.naturalLabel}</label>
        <div className="natural-input">
          <textarea id="trip-description" value={text} onChange={event => setText(event.target.value)}
            rows={2} minLength={3} maxLength={2000} placeholder={copy.search.naturalPlaceholder} required disabled={disabled} />
          <button type="submit" className="button button-secondary" disabled={disabled || !text.trim() || meta?.hosted_agents.configured === false}>
            {parsing ? copy.search.parsing : copy.search.parse}<Icon name="arrow" />
          </button>
        </div>
      </form>
      <ErrorNotice message={parseError} />
    </details>
    {parsed && <div className="parsed-search" aria-live="polite">
      <h3 ref={parsedHeading} tabIndex={-1}>{copy.search.parsed}</h3>
      <p>{parsed.explanation}</p><p>{copy.search.parsedNote}</p>
      <dl className="parsed-fields">
        <div><dt>{copy.search.origin}</dt><dd>{params.origin}</dd></div>
        <div><dt>{copy.search.arrival}</dt><dd>{params.arrival}</dd></div>
        <div><dt>{copy.search.departure}</dt><dd>{params.departure}</dd></div>
        <div><dt>{copy.search.adults} / {copy.search.children}</dt><dd>{params.adults} / {params.children}</dd></div>
        <div><dt>{copy.search.budget}</dt><dd>{copy.search.budgets[params.budget]}</dd></div>
        <div><dt>{copy.search.pace}</dt><dd>{copy.search.paces[params.pace]}</dd></div>
        <div><dt>{copy.search.choices}</dt><dd>{[...params.interests, ...params.regions].join(", ")}</dd></div>
      </dl>
    </div>}
    <form onSubmit={submit} className="structured-form" aria-label={copy.search.structured}>
      <fieldset disabled={disabled}>
        <legend className="sr-only">{copy.search.structured}</legend>
        <div className="search-primary-grid">
          <div className="field origin-field"><label htmlFor="origin"><Icon name="plane" />{copy.search.origin}</label>
            <input id="origin" autoComplete="off" value={params.origin} onChange={event => set("origin", event.target.value)}
              placeholder={copy.search.originPlaceholder} maxLength={80} required />
          </div>
          <div className="field"><label htmlFor="arrival">{copy.search.arrival}</label>
            <input type="date" id="arrival" value={params.arrival} onChange={event => set("arrival", event.target.value)} required />
          </div>
          <div className="field"><label htmlFor="departure">{copy.search.departure}</label>
            <input type="date" id="departure" value={params.departure} onChange={event => set("departure", event.target.value)} required />
          </div>
        </div>
        <div className="search-secondary-grid">
          <div className="field"><label htmlFor="adults">{copy.search.adults}</label>
            <input type="number" id="adults" min="1" max="12" value={params.adults} onChange={event => set("adults", Number(event.target.value))} required />
          </div>
          <div className="field"><label htmlFor="children">{copy.search.children}</label>
            <input type="number" id="children" min="0" max="11" value={params.children} onChange={event => set("children", Number(event.target.value))} required />
          </div>
          <div className="field"><label htmlFor="budget">{copy.search.budget}</label>
            <select id="budget" value={params.budget} onChange={event => {
              const value = event.target.value;
              if (value === "economy" || value === "mid-range" || value === "premium") set("budget", value);
            }}>{Object.entries(copy.search.budgets).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          </div>
          <div className="field"><label htmlFor="pace">{copy.search.pace}</label>
            <select id="pace" value={params.pace} onChange={event => {
              const value = event.target.value;
              if (value === "relaxed" || value === "balanced" || value === "packed") set("pace", value);
            }}>{Object.entries(copy.search.paces).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          </div>
        </div>
        <fieldset className="interest-fieldset"><legend>{copy.search.interests}</legend>
          <div className="choice-chips">{interestIds.map(interest => <label key={interest} className="choice-chip">
            <input type="checkbox" checked={params.interests.includes(interest)} onChange={() => toggle("interests", interest)} />
            <span><Icon name="check" />{copy.search.interestNames[interest]}</span>
          </label>)}</div>
        </fieldset>
        <details className="regions">
          <summary>{copy.search.regions}{params.regions.length > 0 && <span className="badge">{params.regions.length}</span>}</summary>
          <p>{copy.search.regionHelp}</p>
          <fieldset><legend className="sr-only">{copy.search.regions}</legend><div className="choice-chips">
            {regionIds.map(region => <label className="choice-chip" key={region}>
              <input type="checkbox" checked={params.regions.includes(region)} onChange={() => toggle("regions", region)} />
              <span><Icon name="check" />{copy.search.regionNames[region]}</span>
            </label>)}
          </div></fieldset>
        </details>
        <ErrorNotice message={validation ?? error} />
        <div className="search-actions">
          <span className="quiet-label"><Icon name="shield" />{copy.search.seed}</span>
          <button type="submit" className="button button-primary button-large" disabled={disabled}>
            {busy ? copy.search.searching : parsed ? copy.search.confirm : copy.search.submit}<Icon name="arrow" />
          </button>
        </div>
      </fieldset>
    </form>
  </section>;
}
