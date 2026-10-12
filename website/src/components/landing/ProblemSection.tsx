import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { Frame, SectionIntro, useInView, usePrefersReducedMotion } from './ui';

// The design spec's token model for a 40-field form (a model, not a measurement).
const WITHOUT = { calls: 138, tokens: 5.0 };
const WITH = { calls: 8, tokens: 0.18 };
const RACE_SECONDS = 7.5;

const CAMPAIGN_LABELS = [
  'Campaign name',
  'UTM campaign',
  'Daily budget',
  'Start date',
  'Objective',
  'Target country',
  'Region',
  'Audience segment',
  'Placement',
  'Bid strategy',
  'Ad copy',
  'Creative headline',
];

const WITHOUT_LINES = Array.from({ length: WITHOUT.calls }, (_, index) => {
  const label = CAMPAIGN_LABELS[Math.floor(index / 3) % CAMPAIGN_LABELS.length];
  const kind = index % 3;
  if (kind === 0) return { tool: 'screenshot', text: 'find the next field' };
  if (kind === 1) return { tool: 'click', text: `“${label}”` };
  return { tool: 'type', text: 'value, then check the page again' };
});

const WITH_LINES = [
  { tool: 'read', text: 'SKILL.md · acme-campaign-new' },
  { tool: 'navigate', text: 'app.acme.example/campaigns/new' },
  { tool: 'read', text: 'references/fill.md' },
  { tool: 'javascript', text: 'run(values) · every key reported' },
  { tool: 'ask', text: 'once, for the missing budget and audience' },
  { tool: 'javascript', text: 'run({ daily_budget, audience })' },
  { tool: 'click', text: '“Launch campaign”' },
  { tool: 'report', text: '“Campaign scheduled”' },
];

function useRaceClock(isRunning: boolean, runId: number, isReduced: boolean): number {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (isReduced) {
      setProgress(1);
      return undefined;
    }
    if (!isRunning) return undefined;
    setProgress(0);
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const value = Math.min(1, (now - start) / (RACE_SECONDS * 1000));
      setProgress(value);
      if (value < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [isRunning, runId, isReduced]);
  return progress;
}

function Lane({
  title,
  subtitle,
  lines,
  shown,
  calls,
  tokens,
  isSkill,
}: {
  title: string;
  subtitle: string;
  lines: { tool: string; text: string }[];
  shown: number;
  calls: number;
  tokens: number;
  isSkill: boolean;
}): JSX.Element {
  const logRef = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [shown]);

  return (
    <div className="flex min-w-0 flex-col">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4 sm:px-6">
        <div>
           <p className={clsx('text-[0.95rem]', isSkill ? 'text-white/90' : 'text-white/60')}>{title}</p>
           <p className="mt-0.5 font-mono text-[0.68rem] uppercase tracking-[0.13em] text-white/30">{subtitle}</p>
        </div>
        <span
          className={clsx(
            'h-2 w-2 rounded-full',
            shown < lines.length ? (isSkill ? 'animate-pulse bg-galaxy-300' : 'animate-pulse bg-white/60') : 'bg-white/20',
          )}
          aria-hidden="true"
        />
      </div>
      <ol
        ref={logRef}
         className="h-[15.5rem] overflow-hidden px-5 py-4 font-mono text-[0.78rem] leading-[1.7rem] sm:px-6"
        aria-hidden="true"
      >
        {lines.slice(0, shown).map((line, index) => (
          <li key={index} className="flex gap-3 whitespace-nowrap animate-fade-up [animation-duration:0.35s]">
            <span className="w-7 shrink-0 text-right text-white/20">{index + 1}</span>
            <span className={clsx('w-[5.6rem] shrink-0', isSkill ? 'text-galaxy-300' : 'text-white/50')}>{line.tool}</span>
             <span className="truncate text-white/50">{line.text}</span>
          </li>
        ))}
      </ol>
      <div className="mt-auto grid grid-cols-2 border-t border-white/[0.06]">
        <div className="border-r border-white/[0.06] px-5 py-5 sm:px-6">
           <p className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-white/30">Tool calls</p>
           <p className={clsx('mt-2 text-[2.25rem] font-light leading-none tracking-[-0.04em] tabular-nums', isSkill ? 'text-white/90' : 'text-white/60')}>
            ~{calls}
          </p>
        </div>
        <div className="px-5 py-5 sm:px-6">
           <p className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-white/30">Input tokens</p>
           <p className={clsx('mt-2 text-[2.25rem] font-light leading-none tracking-[-0.04em] tabular-nums', isSkill ? 'text-galaxy-200' : 'text-white/60')}>
            ~{tokens.toFixed(tokens < 1 ? 2 : 1)}M
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ProblemSection(): JSX.Element {
  const [ref, isInView] = useInView<HTMLDivElement>({ threshold: 0.35 }, true);
  const [runId, setRunId] = useState(0);
  const isReduced = usePrefersReducedMotion();
  const progress = useRaceClock(isInView, runId, isReduced);

  // Computer use takes the whole race; the skill is done in the first third.
  const withoutShown = Math.round(progress * WITHOUT.calls);
  const skillProgress = Math.min(1, progress * 2.6);
  const withShown = Math.round(skillProgress * WITH.calls);

  return (
    <section id="why" className="sg-section sg-tone-blue relative py-28 sm:py-36" aria-labelledby="why-title">
      <div className="sg-shell">
        <SectionIntro
          index="01"
          tag="The problem"
          id="why-title"
          title={
            <>
              Every task, the AI meets
              <br className="hidden sm:block" /> your form for the first time.
            </>
          }
          lede="Without a skill it screenshots, clicks field by field and guesses which options exist. With one, it already knows every field, rule and dependency, and fills the page in a single call."
        />

        <div ref={ref} className="mt-16">
          <Frame>
            <div className="sg-race sg-window grid border border-white/[0.07] bg-[#0b0b0e] md:grid-cols-2">
              <div className="border-b border-white/[0.06] md:border-b-0 md:border-r">
                <Lane
                  title="Computer use"
                  subtitle="40-field form · no skill"
                  lines={WITHOUT_LINES}
                  shown={withoutShown}
                  calls={Math.max(0, withoutShown)}
                  tokens={WITHOUT.tokens * progress}
                  isSkill={false}
                />
              </div>
              <Lane
                title="With a generated skill"
                subtitle="40-field campaign form · acme-campaign-new"
                lines={WITH_LINES}
                shown={withShown}
                calls={withShown}
                tokens={WITH.tokens * skillProgress}
                isSkill
              />
            </div>
          </Frame>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
             <p className="max-w-2xl text-[0.875rem] leading-relaxed text-white/30">
              Modelled from the design spec for a 40-field form: about 138 calls and 5.0M input tokens against
              about 8 calls and 0.18M, roughly 25× fewer. A model, not a measurement yet.
            </p>
            <button
              type="button"
              onClick={() => setRunId((value) => value + 1)}
               className="font-mono text-[0.75rem] uppercase tracking-[0.14em] text-white/40 transition-colors hover:text-white/90"
            >
              ↻ Replay
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
