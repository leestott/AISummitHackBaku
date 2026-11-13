import type { CSSProperties } from "react";

const paths = {
  compass: <><circle cx="12" cy="12" r="9" /><path d="m16 7-3 6-6 4 4-6Z" /></>,
  arrow: <><path d="M4 12h15m-6-6 6 6-6 6" /></>,
  back: <><path d="M20 12H5m6-6-6 6 6 6" /></>,
  plane: <path d="m21 3-6 18-4-8-8-4Zm-10 10L21 3" />,
  bed: <><path d="M3 18V8m18 10V9M3 14h18M3 9h18M3 18v3m18-3v3M6 9V5h12v4" /></>,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z" /><circle cx="12" cy="10" r="2" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v5m10-5v5M3 11h18m-13 4h2m4 0h2" /></>,
  people: <><circle cx="9" cy="7" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5v2" /></>,
  check: <path d="m5 12 4 4L20 5" />,
  checklist: <><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4V2h6v2m-7 8 2 2 5-5m-6 9h6" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10h.01" /></>,
  warning: <><path d="m12 3 10 18H2Zm0 6v5m0 3h.01" /></>,
  bus: <><rect x="5" y="3" width="14" height="16" rx="3" /><path d="M5 12h14M8 19v3m8-3v3M8 16h.01M16 16h.01M9 6h6" /></>,
  walk: <><circle cx="14" cy="4" r="2" /><path d="m8 10 4-3 4 5 4 1m-8-6-2 8-5 5m5-5 6 2 1 5" /></>,
  star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3L7.5 14 3 9.6l6.2-.9Z" />,
  map: <><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16" /></>,
  list: <><path d="M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  up: <path d="m6 14 6-6 6 6" />,
  down: <path d="m6 10 6 6 6-6" />,
  drag: <path d="M9 5h.01M15 5h.01M9 12h.01M15 12h.01M9 19h.01M15 19h.01" />,
  trash: <><path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>,
  external: <><path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7" /></>,
  chat: <path d="M21 11a9 9 0 0 1-9 9H3l2-5a9 9 0 1 1 16-4Z" />,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
  shield: <><path d="m12 2 8 3v7c0 5-8 10-8 10S4 17 4 12V5Z" /><path d="m8 12 3 3 5-6" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2" /></>,
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, className = "", style }: { name: IconName; className?: string; style?: CSSProperties }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={`icon ${className}`} style={style}>
    {paths[name]}
  </svg>;
}
