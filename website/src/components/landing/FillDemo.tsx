import React, { useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import { Frame, SectionIntro, StatusChip, Window, useInView, usePrefersReducedMotion } from './ui';

type FieldKind = 'text' | 'radio' | 'select' | 'combobox' | 'tree' | 'textarea' | 'checkbox';

type Field = {
  key: string;
  label: string;
  kind: FieldKind;
  value: string;
  waitsFor?: string;
  options?: string[];
  /** How references/locators.md finds it. */
  locator: string;
  /** What references/locators.md does to it. */
  act: string;
  /** Which "Fill with browser actions" rule in SKILL.md applies. */
  rule: number;
  /** Which step of references/manual-steps.md it belongs to. */
  step: number;
};

// A New campaign form in a marketing app: its fields, option lists, and the
// locators, browser-action rules and manual steps its generated skill ships.
const FIELDS: Field[] = [
  { key: 'campaign_name', label: 'Campaign name', kind: 'text', value: 'Spring Sale 2026', locator: "getByRole('textbox', { name: 'Campaign name' })", act: "fill('Spring Sale 2026')", rule: 0, step: 1 },
  { key: 'utm_campaign', label: 'UTM campaign', kind: 'text', value: 'spring_sale_2026', locator: "getByRole('textbox', { name: 'UTM campaign' })", act: "fill('spring_sale_2026')", rule: 0, step: 1 },
  { key: 'daily_budget', label: 'Daily budget (USD)', kind: 'text', value: '250', locator: "getByRole('spinbutton', { name: 'Daily budget (USD)' })", act: "fill('250')", rule: 0, step: 1 },
  { key: 'start_date', label: 'Start date', kind: 'text', value: '2026-03-02', locator: "getByLabel('Start date')", act: "fill('2026-03-02')", rule: 0, step: 1 },
  {
    key: 'objective',
    label: 'Objective',
    kind: 'radio',
    value: 'Leads',
    options: ['Awareness', 'Traffic', 'Leads', 'Sales'],
    locator: "getByRole('radio', { name: 'Leads' })",
    act: 'check()',
    rule: 2,
    step: 2,
  },
  {
    key: 'country',
    label: 'Target country',
    kind: 'select',
    value: 'United States',
    options: ['Canada', 'Germany', 'United Kingdom', 'United States'],
    locator: "getByRole('combobox', { name: 'Target country' })",
    act: "selectOption({ label: 'United States' })",
    rule: 1,
    step: 3,
  },
  {
    key: 'region',
    label: 'Region',
    kind: 'select',
    value: 'West Coast',
    waitsFor: 'country',
    options: ['Midwest', 'Northeast', 'South', 'West Coast'],
    locator: "getByRole('combobox', { name: 'Region' })",
    act: "selectOption({ label: 'West Coast' })",
    rule: 1,
    step: 3,
  },
  {
    key: 'audience',
    label: 'Audience segment',
    kind: 'combobox',
    value: 'Newsletter subscribers',
    options: ['Cart abandoners', 'Lookalike: past buyers', 'Newsletter subscribers', 'Website visitors (30 days)'],
    locator: "getByRole('combobox', { name: 'Audience segment' })",
    act: "fill('Newsletter subscribers'), then click the option",
    rule: 3,
    step: 3,
  },
  {
    key: 'placement',
    label: 'Placement',
    kind: 'tree',
    value: 'Social / Instagram / Stories',
    options: ['Social', 'Instagram', 'Stories'],
    locator: "getByRole('tree', { name: 'Placement' })",
    act: 'click() each level of the path',
    rule: 4,
    step: 4,
  },
  {
    key: 'ad_copy',
    label: 'Ad copy',
    kind: 'textarea',
    value: 'Spring savings are here: 20% off your first order.',
    locator: "getByRole('textbox', { name: 'Ad copy' })",
    act: 'click(), then type the text',
    rule: 5,
    step: 5,
  },
  {
    key: 'agree_policy',
    label: 'I agree to the advertising policy',
    kind: 'checkbox',
    value: 'yes',
    locator: "getByRole('checkbox', { name: 'I agree…' })",
    act: 'check()',
    rule: 6,
    step: 6,
  },
];

// "Fill with browser actions", as the campaign skill's SKILL.md words it.
const ACTION_RULES = [
  'Text, dates and numbers: click the field, type the value.',
  'A drop-down list: choose the option by its visible text.',
  'Options shown side by side: click each wanted one by its label.',
  'A search box with a list: type the value, wait, then pick it from the list.',
  'A tree: open it and click each level of the path in turn.',
  'A text editor: click inside it and type.',
  'A yes/no box: tick it for yes, clear it for no.',
];

// The steps of references/manual-steps.md, abridged; step 0 opens the page.
const MANUAL_STEPS = [
  'Open the page.',
  'Campaign details: name, UTM tag, daily budget, start date.',
  'Objective: choose what the campaign is for.',
  'Targeting: country, then region once its list fills in, then audience.',
  'Placement: open the placement tree, pick each level in turn.',
  'Ad copy: click inside the editor and type it.',
  'Accept the advertising policy, read every value back.',
];

const REGION_LOAD_MS = 600;

type MethodId = 'javascript' | 'locators' | 'actions' | 'manual';

type Method = {
  id: MethodId;
  name: string;
  file: string;
  summary: string;
  stepMs: number;
  overlapMs: number;
  /** Share of each field's time spent finding it before anything is written. */
  lead: number;
};

const METHODS: Method[] = [
  {
    id: 'javascript',
    name: 'JavaScript in the page',
    file: 'references/fill.md',
    summary: 'For tools that can run a script in the page. One call sets every field through the page’s own setters and reports each key back.',
    stepMs: 300,
    overlapMs: 220,
    lead: 0,
  },
  {
    id: 'locators',
    name: 'Locators',
    file: 'references/locators.md',
    summary: 'For tools that act on elements by role and accessible name, the way the accessibility tree describes them. Data, not code.',
    stepMs: 780,
    overlapMs: 0,
    lead: 0.38,
  },
  {
    id: 'actions',
    name: 'Browser actions',
    file: 'SKILL.md · Fill with browser actions',
    summary: 'For agents that see the page and drive the mouse and keyboard: click and type each field by its visible label, in table order.',
    stepMs: 820,
    overlapMs: 0,
    lead: 0.32,
  },
  {
    id: 'manual',
    name: 'By hand',
    file: 'references/manual-steps.md',
    summary: 'When nothing automated works: numbered steps by labels and sections, for an AI to follow from screenshots, or for the user.',
    stepMs: 900,
    overlapMs: 0,
    lead: 0.2,
  },
];

type Timing = { start: number; end: number };

function planTimeline(method: Method): { timings: Record<string, Timing>; total: number } {
  const timings: Record<string, Timing> = {};
  let cursor = 450;
  FIELDS.forEach((field) => {
    let start = cursor;
    if (field.waitsFor) start = Math.max(start, timings[field.waitsFor].end + REGION_LOAD_MS);
    timings[field.key] = { start, end: start + method.stepMs };
    cursor = start + method.stepMs - method.overlapMs;
  });
  const total = Math.max(...Object.values(timings).map((timing) => timing.end)) + 300;
  return { timings, total };
}

function useTimeline(total: number, isPlaying: boolean, runKey: string, isReduced: boolean): number {
  // The time belongs to the run that produced it, so a new method never
  // renders a frame with the previous method's clock.
  const [clock, setClock] = useState({ key: runKey, value: 0 });
  useEffect(() => {
    if (isReduced) {
      setClock({ key: runKey, value: total });
      return undefined;
    }
    if (!isPlaying) return undefined;
    setClock({ key: runKey, value: 0 });
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const value = now - start;
      setClock({ key: runKey, value: Math.min(value, total) });
      if (value < total) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [total, isPlaying, runKey, isReduced]);
  if (isReduced) return total;
  return clock.key === runKey ? clock.value : 0;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

type FieldState = {
  /** 0..1 through the field's whole slot. */
  slot: number;
  /** 0..1 through the writing part, after the field was found. */
  write: number;
  isActive: boolean;
  isDone: boolean;
  isLoading: boolean;
};

function readFieldState(field: Field, method: Method, timings: Record<string, Timing>, elapsed: number): FieldState {
  const timing = timings[field.key];
  const slot = clamp01((elapsed - timing.start) / (timing.end - timing.start));
  const write = method.lead ? clamp01((slot - method.lead) / (1 - method.lead)) : slot;
  const waiting = field.waitsFor ? timings[field.waitsFor] : null;
  return {
    slot,
    write,
    isActive: slot > 0 && slot < 1,
    isDone: slot >= 1,
    isLoading: Boolean(waiting && elapsed >= waiting.end && elapsed < timing.start),
  };
}

/* ------------------------------------------------------------ form pieces */

function OptionsPopover({ field, state, method }: { field: Field; state: FieldState; method: Method }): JSX.Element | null {
  if (method.id === 'javascript' || !state.isActive || !field.options || field.kind === 'radio') return null;
  if (state.slot < method.lead * 0.6) return null;

  if (field.kind === 'tree') {
    const levels = field.options;
    const reached = Math.floor(state.write * (levels.length + 0.5));
    return (
      <div className="absolute left-0 top-[calc(100%+4px)] z-30 w-[min(20rem,100%)] animate-fade-up border border-white/15 bg-[#121216] p-2 shadow-2xl [animation-duration:0.25s]">
        {levels.map((level, index) => (
          <div
            key={level}
            className={clsx(
               'flex items-center gap-2 px-2 py-1 text-[0.78rem] transition-colors duration-200',
               index < reached ? 'text-white/90' : 'text-white/30',
              index === reached - 1 && 'bg-galaxy-500/20',
            )}
            style={{ paddingLeft: `${0.5 + index * 0.9}rem` }}
          >
            <span className="text-white/40">{index < levels.length - 1 ? (index < reached ? '▾' : '▸') : '·'}</span>
            {level}
          </div>
        ))}
      </div>
    );
  }

  const chosenAt = field.kind === 'combobox' ? 0.75 : 0.45;
  const isChosen = state.write >= chosenAt;
  const typed = field.kind === 'combobox' ? field.value.slice(0, Math.round(field.value.length * clamp01(state.write / 0.6))) : '';
  const options = field.kind === 'combobox' ? field.options.filter((option) => option.toLowerCase().startsWith(typed.slice(0, 1).toLowerCase()) || !typed) : field.options;
  return (
    <div className="absolute left-0 top-[calc(100%+4px)] z-30 w-full animate-fade-up border border-white/15 bg-[#121216] py-1 shadow-2xl [animation-duration:0.25s]">
      {options.map((option) => {
        const isTarget = option === field.value;
        return (
          <div
            key={option}
            className={clsx(
               'px-3 py-1 text-[0.78rem] transition-colors duration-200',
               isTarget && isChosen ? 'bg-galaxy-500/30 text-white/90' : isTarget && state.write > 0.2 ? 'bg-white/[0.06] text-white/80' : 'text-white/40',
            )}
          >
            {option}
          </div>
        );
      })}
    </div>
  );
}

function FieldControl({ field, state, method }: { field: Field; state: FieldState; method: Method }): JSX.Element {
  const isFinding = method.lead > 0 && state.isActive && state.slot < method.lead;
  const isWriting = state.isActive && !isFinding;
  const box = clsx(
     'relative flex h-8 items-center border px-3 text-[0.82rem] transition-[border-color,box-shadow,background-color] duration-300',
    isWriting ? 'border-galaxy-300/80 shadow-[0_0_0_3px_rgba(100,130,255,0.18)]' : 'border-white/[0.12]',
  );

  if (field.kind === 'radio') {
    return (
       <div className="flex h-8 items-center gap-5 text-[0.82rem] text-white/60">
        {field.options?.map((option) => {
          const isChosen = state.write >= 0.6 && option === field.value;
          return (
            <span key={option} className="flex items-center gap-2">
              <span className={clsx('flex h-3.5 w-3.5 items-center justify-center rounded-full border transition-colors', isChosen ? 'border-galaxy-300' : 'border-white/30')}>
                {isChosen && <span className="h-1.5 w-1.5 rounded-full bg-galaxy-300" />}
              </span>
              {option}
            </span>
          );
        })}
      </div>
    );
  }

  if (field.kind === 'checkbox') {
    const isTicked = state.write >= 0.6 || state.isDone;
    return (
       <span className="flex h-7 items-center gap-2.5 text-[0.82rem] text-white/60">
        <span className={clsx('flex h-3.5 w-3.5 items-center justify-center border transition-colors', isTicked ? 'border-galaxy-300 bg-galaxy-400' : 'border-white/30')}>
          {isTicked && (
            <svg viewBox="0 0 12 12" className="h-2.5 w-2.5 text-[#0a0a0c]" aria-hidden="true">
              <path d="M2.5 6.5l2.2 2.2 4.8-5.2" stroke="currentColor" strokeWidth="1.8" fill="none" />
            </svg>
          )}
        </span>
        {field.label}
      </span>
    );
  }

  const isTyped = field.kind === 'text' || field.kind === 'textarea';
  let shown = '';
  if (isTyped) shown = field.value.slice(0, Math.round(field.value.length * state.write));
  else if (field.kind === 'combobox') shown = state.write >= 0.75 || state.isDone ? field.value : field.value.slice(0, Math.round(field.value.length * clamp01(state.write / 0.6)));
  else if (state.isDone || (method.id === 'javascript' ? state.write >= 0.5 : state.write >= 0.55)) shown = field.value;

  const placeholder = field.kind === 'select' || field.kind === 'tree' ? 'Choose…' : '';
  return (
    <div className={clsx(box, field.kind === 'textarea' && 'h-11 items-start pt-1.5')}>
      <span className={clsx('truncate', shown ? 'text-white/90' : 'text-white/30')}>
        {state.isLoading ? 'Loading…' : shown || placeholder}
      </span>
      {isWriting && (isTyped || field.kind === 'combobox') && state.write < 1 && (
        <span className="ml-px h-3.5 w-px animate-blink bg-galaxy-200" aria-hidden="true" />
      )}
      {(field.kind === 'select' || field.kind === 'tree') && (
        <span className="ml-auto pl-2 text-[0.72rem] text-white/30" aria-hidden="true">
          ▾
        </span>
      )}
    </div>
  );
}

/** The locator a tool would use, drawn on the field it finds. */
function LocatorMark({ field, state, method }: { field: Field; state: FieldState; method: Method }): JSX.Element | null {
  if (method.id !== 'locators' || !state.isActive) return null;
  const isFound = state.slot >= method.lead * 0.55;
  return (
    <>
      <span
        aria-hidden="true"
        className={clsx(
          'pointer-events-none absolute -inset-1.5 z-10 border border-dashed transition-all duration-300',
          isFound ? 'border-galaxy-300 bg-galaxy-500/[0.06]' : 'scale-105 border-white/40 opacity-60',
        )}
      />
       <span className="pointer-events-none absolute -top-[1.35rem] right-0 z-20 max-w-full animate-fade-up truncate bg-galaxy-500 px-1.5 py-0.5 font-mono text-[0.68rem] text-white [animation-duration:0.25s]">
        {state.slot < method.lead ? field.locator : `.${field.act.split(',')[0]}`}
      </span>
    </>
  );
}

/* ------------------------------------------------------------ the stage */

type Point = { x: number; y: number };

function FormStage({
  method,
  timings,
  total,
  elapsed,
}: {
  method: Method;
  timings: Record<string, Timing>;
  total: number;
  elapsed: number;
}): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const fieldRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [cursor, setCursor] = useState<Point>({ x: 40, y: 40 });

  const states = useMemo(
    () => Object.fromEntries(FIELDS.map((field) => [field.key, readFieldState(field, method, timings, elapsed)])),
    [method, timings, elapsed],
  );
  const activeField = FIELDS.find((field) => states[field.key].isActive);
  const doneCount = FIELDS.filter((field) => states[field.key].isDone).length;
  const isFinished = elapsed >= total;

  // The cursor glides to whichever field browser actions are working on.
  useEffect(() => {
    if (method.id !== 'actions') return;
    const container = containerRef.current;
    const node = activeField ? fieldRefs.current[activeField.key] : null;
    if (!container || !node) return;
    const outer = container.getBoundingClientRect();
    const inner = node.getBoundingClientRect();
    const control = node.lastElementChild?.getBoundingClientRect() ?? inner;
    setCursor({ x: control.left - outer.left + Math.min(46, control.width / 2), y: control.top - outer.top + control.height / 2 });
  }, [activeField, method.id]);

  const activeStep = activeField ? activeField.step : isFinished ? MANUAL_STEPS.length : 0;
  const scanTop = clamp01(elapsed / Math.max(1, total - 300)) * 100;

  return (
    <div className="relative">
      <div ref={containerRef} className="relative grid gap-x-4 gap-y-2.5 p-5 sm:grid-cols-2 sm:p-6">
         <p className="text-[0.9rem] font-medium text-white/90 sm:col-span-2">New campaign</p>
        {FIELDS.map((field) => {
          const state = states[field.key];
          const isWide = field.kind === 'textarea' || field.kind === 'checkbox' || field.kind === 'tree' || field.kind === 'radio';
          return (
            <div
              key={field.key}
              ref={(node) => {
                fieldRefs.current[field.key] = node;
              }}
              className={clsx(
                'relative transition-opacity duration-500',
                isWide && 'sm:col-span-2',
                state.isActive && 'z-20',
                // By hand, a person works one section at a time.
                method.id === 'manual' && !isFinished && elapsed > 0 && field.step !== activeStep && 'opacity-30',
              )}
            >
              {field.kind !== 'checkbox' && (
                 <p className={clsx('mb-1 text-[0.72rem] transition-colors', state.isActive && method.id !== 'javascript' ? 'text-white/90' : 'text-white/40')}>
                  {field.label}
                </p>
              )}
              <div className="relative">
                <LocatorMark field={field} state={state} method={method} />
                <FieldControl field={field} state={state} method={method} />
                <OptionsPopover field={field} state={state} method={method} />
              </div>
            </div>
          );
        })}
        <div className="flex items-center justify-between gap-4 pt-1 sm:col-span-2">
           <span className="font-mono text-[0.68rem] text-white/30">
            {doneCount}/{FIELDS.length} set
          </span>
           <span className={clsx('px-4 py-1.5 text-[0.8rem] transition-colors duration-500', isFinished ? 'bg-white text-[#0a0a0c]' : 'bg-white/[0.08] text-white/40')}>
            Launch campaign
          </span>
        </div>

        {/* JavaScript: one call, one sweep down the page. */}
        {method.id === 'javascript' && elapsed > 0 && !isFinished && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 z-10 h-16 -translate-y-1/2 bg-gradient-to-b from-transparent via-galaxy-400/20 to-transparent"
            style={{ top: `${scanTop}%` }}
          >
            <span className="absolute inset-x-0 top-1/2 h-px bg-galaxy-300/70 shadow-[0_0_14px_rgba(140,166,255,0.9)]" />
          </span>
        )}

        {/* Browser actions: a pointer that clicks and types. */}
        {method.id === 'actions' && !isFinished && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-0 top-0 z-40 transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
            style={{ transform: `translate(${cursor.x}px, ${cursor.y}px)` }}
          >
            {activeField && states[activeField.key].slot > method.lead * 0.85 && states[activeField.key].slot < method.lead + 0.2 && (
              <span className="absolute -left-3 -top-3 h-6 w-6 animate-ping rounded-full border border-galaxy-300" />
            )}
            <svg viewBox="0 0 16 20" className="h-5 w-4 drop-shadow-[0_2px_6px_rgba(0,0,0,0.8)]">
              <path d="M1 1l13 10.5-6.2.6 3.6 6.6-2.4 1.2-3.5-6.7L1 17.7z" fill="#fff" stroke="#0a0a0c" strokeWidth="1" />
            </svg>
          </span>
        )}

      </div>

      <StatusBar method={method} activeField={activeField} states={states} isFinished={isFinished} elapsed={elapsed} activeStep={activeStep} />
    </div>
  );
}

function StatusBar({
  method,
  activeField,
  states,
  isFinished,
  elapsed,
  activeStep,
}: {
  method: Method;
  activeField: Field | undefined;
  states: Record<string, FieldState>;
  isFinished: boolean;
  elapsed: number;
  activeStep: number;
}): JSX.Element {
  let line: React.ReactNode = null;
  if (method.id === 'javascript') {
    const done = FIELDS.filter((field) => states[field.key].isDone);
    line = (
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
         <span className="text-white/40">layout</span>
        <StatusChip status={elapsed > 350 ? 'match' : '…'} />
         <span className="ml-2 text-white/40">fill</span>
        {done.map((field) => (
          <span key={field.key} className="flex animate-fade-up items-center gap-1 [animation-duration:0.3s]">
            <span className="text-white/40">{field.key}</span>
            <StatusChip status="ok" />
          </span>
        ))}
      </div>
    );
  } else if (method.id === 'locators') {
    line = activeField ? (
      <p className="truncate">
         <span className="text-white/30">await page.</span>
        <span className="text-galaxy-200">{activeField.locator}</span>
        {states[activeField.key].slot >= method.lead && <span className="text-[#a5d6ff]">.{activeField.act}</span>}
      </p>
    ) : (
       <p className="text-white/50">{isFinished ? 'Every field found by role and name, then read back before submit.' : 'Finding the first field…'}</p>
    );
  } else if (method.id === 'actions') {
    const state = activeField ? states[activeField.key] : null;
    const verb =
      !activeField || !state
        ? ''
        : state.slot < method.lead
          ? `move to “${activeField.label}”`
          : activeField.kind === 'select'
            ? `choose “${activeField.value}”`
            : activeField.kind === 'tree'
              ? `click ${activeField.value.split(' / ').map((level) => `“${level}”`).join(' › ')}`
              : activeField.kind === 'radio' || activeField.kind === 'checkbox'
                ? `click “${activeField.kind === 'radio' ? activeField.value : 'I agree…'}”`
                : `click “${activeField.label}”, type “${activeField.value}”`;
     line = <p className="truncate text-white/60">{activeField ? verb : isFinished ? 'Every field set by its visible label. Values read back.' : 'Reading the field table…'}</p>;
  } else {
    line = (
      <div className="flex items-center gap-3">
        <ol className="flex shrink-0 items-center gap-1" aria-hidden="true">
          {MANUAL_STEPS.map((step, index) => {
            const isDone = isFinished || index < activeStep || (index === 0 && elapsed > 200);
            const isCurrent = index === activeStep && !isFinished;
            return (
              <li
                key={step}
                className={clsx(
                  'flex h-5 w-5 items-center justify-center border text-[0.72rem] transition-colors duration-300',
                   isDone ? 'border-galaxy-300 bg-galaxy-400 text-[#0a0a0c]' : isCurrent ? 'border-galaxy-300 text-white/90' : 'border-white/20 text-white/30',
                )}
              >
                {isDone ? '✓' : index + 1}
              </li>
            );
          })}
        </ol>
           <p className="min-w-0 truncate text-white/60">
          {isFinished ? 'Done by hand, step by step. Ready to submit.' : MANUAL_STEPS[Math.min(activeStep, MANUAL_STEPS.length - 1)]}
        </p>
      </div>
    );
  }

  return (
     <div className="flex h-[3.25rem] items-center border-t border-white/[0.07] bg-black/40 px-5 font-mono text-[0.72rem]" aria-live="polite">
      <div className="min-w-0 flex-1">{line}</div>
    </div>
  );
}

/* ------------------------------------------------------------ left panel */

function SourcePanel({ method, activeField, states }: { method: Method; activeField: Field | undefined; states: Record<string, FieldState> }): JSX.Element {
  if (method.id === 'javascript') {
    return (
      <div className="space-y-0.5">
         <p className="text-white/30">// javascript_tool, once</p>
        <p className="text-white/70">await (async function (S, M, G, V, O) {'{ … }'})(</p>
        <p className="pl-4 text-[#a5d6ff]">"acme-campaign-new",</p>
         <p className="pl-4 text-white/40">[["campaign_name","#campaign_name","i"], …],</p>
         <p className="pl-4 text-white/40">{'{"w":1280,"h":900,"a":"campaign_name", …},'}</p>
        <p className="pl-4 text-galaxy-200">{'{"campaign_name":"Spring Sale 2026", "objective":"Leads", …},'}</p>
         <p className="pl-4 text-white/40">{'{}'}</p>
        <p className="text-white/70">)</p>
      </div>
    );
  }
  if (method.id === 'locators') {
    return (
      <table className="w-full table-fixed border-collapse text-left">
        <thead>
          <tr className="text-white/30">
            <th className="w-[34%] pb-1.5 font-normal">key</th>
            <th className="w-[24%] pb-1.5 font-normal">role</th>
            <th className="pb-1.5 font-normal">do</th>
          </tr>
        </thead>
        <tbody>
          {FIELDS.map((field) => {
            const state = states[field.key];
            const role = field.locator.startsWith('getByRole') ? field.locator.split("'")[1] : 'label';
            return (
               <tr key={field.key} className={clsx('transition-colors duration-200', state.isActive ? 'bg-galaxy-500/15 text-white/90' : state.isDone ? 'text-white/50' : 'text-white/25')}>
                <td className="truncate py-[3px] pr-2">{field.key}</td>
                <td className="truncate py-[3px] pr-2">{role}</td>
                <td className="truncate py-[3px]">{field.act.split('(')[0]}()</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
  if (method.id === 'actions') {
    const used = new Set(FIELDS.filter((field) => states[field.key].isDone).map((field) => field.rule));
    return (
      <ul className="space-y-1.5">
        {ACTION_RULES.map((rule, index) => (
          <li
            key={rule}
            className={clsx(
              'flex gap-2 leading-snug transition-colors duration-300',
               activeField?.rule === index ? 'text-white/90' : used.has(index) ? 'text-white/50' : 'text-white/25',
            )}
          >
            <span className={activeField?.rule === index ? 'text-galaxy-300' : 'text-white/25'}>{activeField?.rule === index ? '▸' : '-'}</span>
            {rule}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <div className="space-y-1 text-white/40">
      <p className="text-white/70"># New campaign — by hand</p>
      <p>Plain steps by what the page shows. Take every</p>
      <p>value from the user and never invent one.</p>
       <p className="pt-1 text-white/50">2. **Campaign details**</p>
      <p className="pl-4">- Campaign name: type it (text, 3–80 chars). Required.</p>
      <p className="pl-4">- UTM campaign: type it (lowercase, digits, _).</p>
       <p className="pt-1 text-white/50">4. **Targeting**</p>
      <p className="pl-4">- Region: choose one. Its list fills in after Country.</p>
      <p className="pl-4">- Audience segment: type it, then pick it from the list.</p>
    </div>
  );
}

/* ------------------------------------------------------------ section */

export default function FillDemo(): JSX.Element {
  const [active, setActive] = useState(0);
  const [runCount, setRunCount] = useState(0);
  const [isPinned, setIsPinned] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const [stageRef, isInView] = useInView<HTMLDivElement>({ threshold: 0.25 });
  const isReduced = usePrefersReducedMotion();
  const method = METHODS[active];
  const { timings, total } = useMemo(() => planTimeline(method), [method]);
  const elapsed = useTimeline(total, isInView, `${active}-${runCount}`, isReduced);
  const isFinished = elapsed >= total;

  const states = useMemo(
    () => Object.fromEntries(FIELDS.map((field) => [field.key, readFieldState(field, method, timings, elapsed)])),
    [method, timings, elapsed],
  );
  const activeField = FIELDS.find((field) => states[field.key].isActive);

  // Wide screens pin the stage and let scrolling choose the method.
  useEffect(() => {
    const query = window.matchMedia('(min-width: 1024px)');
    const update = () => setIsPinned(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!isPinned) return undefined;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const track = trackRef.current;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const span = rect.height - window.innerHeight;
      const progress = span > 0 ? clamp01(-rect.top / span) : 0;
      setActive(Math.min(METHODS.length - 1, Math.floor(progress * METHODS.length)));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, [isPinned]);

  // While a reader lingers on one method, it plays again after a pause.
  useEffect(() => {
    if (!isPinned || !isInView || !isFinished || isReduced) return undefined;
    const timer = window.setTimeout(() => setRunCount((value) => value + 1), 3200);
    return () => window.clearTimeout(timer);
  }, [isPinned, isInView, isFinished, isReduced]);

  // Small screens are not pinned: the methods take turns while in view.
  useEffect(() => {
    if (isPinned || !isInView || !isFinished || isReduced) return undefined;
    const timer = window.setTimeout(() => setActive((value) => (value + 1) % METHODS.length), 2200);
    return () => window.clearTimeout(timer);
  }, [isPinned, isInView, isFinished, isReduced]);

  const choose = (index: number) => {
    const track = trackRef.current;
    if (isPinned && track) {
      const top = track.getBoundingClientRect().top + window.scrollY;
      const span = track.offsetHeight - window.innerHeight;
      window.scrollTo({ top: top + span * ((index + 0.5) / METHODS.length), behavior: isReduced ? 'auto' : 'smooth' });
    } else {
      setActive(index);
      setRunCount((value) => value + 1);
    }
  };

  return (
    <section id="fill" className="sg-section sg-band sg-band-blue sg-tone-blue relative pt-28 sm:pt-36 lg:pb-8" aria-labelledby="fill-title">
      <div className="sg-shell">
        <SectionIntro
          index="04"
          tag="At fill time"
          id="fill-title"
          title={
            <>
              One call fills the page.
              <br className="hidden sm:block" /> Three fallbacks if it can’t.
            </>
          }
          lede="Browser agents don’t all work the same way. Some can run a script in the page, some act on elements by their role and label, and some only see screenshots and use the mouse and keyboard. Every skill carries a fill method for each. The AI uses the first one its tools support, and any field that method can’t set moves on to the next, so one skill works in whichever browser the AI has."
        />
      </div>

      <div ref={trackRef} className="relative pb-28 sm:pb-36 lg:h-[400svh] lg:pb-0">
        <div className="lg:sticky lg:top-0 lg:flex lg:h-svh lg:items-center lg:pt-12">
          <div ref={stageRef} className="sg-fill-stage sg-shell mt-14 grid gap-6 lg:mt-0 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:items-center">
            <div className="flex flex-col">
              <div role="tablist" aria-label="Fill methods" className="border-t border-white/[0.07]">
                {METHODS.map((item, index) => {
                  const isSelected = index === active;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      role="tab"
                      aria-selected={isSelected}
                      onClick={() => choose(index)}
                      className={clsx(
                        'group relative flex w-full items-start gap-4 border-b border-white/[0.07] py-4 text-left transition-colors',
                         isSelected ? 'text-white/90' : 'text-white/40 hover:text-white/70',
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className={clsx(
                          'absolute -left-px bottom-0 top-0 w-px transition-colors duration-500',
                          isSelected ? 'bg-galaxy-300 shadow-[0_0_10px_rgba(140,166,255,0.9)]' : 'bg-transparent',
                        )}
                      />
                      <span className={clsx('mt-1 pl-3 font-mono text-[0.82rem]', isSelected ? 'text-galaxy-300' : 'text-white/25')}>
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span className="flex-1">
                         <span className="block text-[1.1rem] font-medium tracking-[-0.02em]">{item.name}</span>
                        <span className={clsx('grid transition-all duration-500', isSelected ? 'mt-1.5 grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
                          <span className="overflow-hidden">
                             <span className="block text-[0.9rem] leading-[1.6] text-white/50">{item.summary}</span>
                          </span>
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="sg-window mt-5 border border-white/[0.07] bg-[#0b0b0e]">
                 <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5 font-mono text-[0.68rem]">
                  <span className="text-galaxy-200/80">{method.file}</span>
                  <span className="text-white/30">in the skill</span>
                </div>
                 <div key={method.id} className="h-[13.5rem] animate-fade-up overflow-hidden px-4 py-3.5 font-mono text-[0.72rem] leading-[1.6] [animation-duration:0.4s]">
                  <SourcePanel method={method} activeField={activeField} states={states} />
                </div>
              </div>

              <div className="mt-5 hidden items-center gap-3 lg:flex" aria-hidden="true">
                <div className="flex gap-1">
                  {METHODS.map((item, index) => (
                    <span
                      key={item.id}
                      className={clsx('h-1 transition-all duration-500', index === active ? 'w-8 bg-galaxy-300' : index < active ? 'w-3 bg-white/40' : 'w-3 bg-white/15')}
                    />
                  ))}
                </div>
                 <span className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-white/30">
                  {active < METHODS.length - 1 ? 'Scroll for the next method' : 'All four, one skill'}
                </span>
              </div>
            </div>

            <Frame tone="accent">
              <Window title="meow-moew.uni/campaigns/new" kind="browser" isSquare>
                <FormStage method={method} timings={timings} total={total} elapsed={elapsed} />
              </Window>
            </Frame>
          </div>
        </div>
      </div>
    </section>
  );
}
