import React, { useEffect, useState } from 'react';
import clsx from 'clsx';
import { Frame, Reveal, SectionIntro, StatusChip, Window, useInView, usePrefersReducedMotion } from './ui';

type Turn =
  | { kind: 'user'; text: string }
  | { kind: 'run'; text: string }
  | { kind: 'result'; status: string; text: string }
  | { kind: 'agent'; text: string };

// A walk-through: a campaign page that needs a sign-in before x/y.
const TURNS: Turn[] = [
  { kind: 'user', text: '/skillgendev /campaigns/42/edit — with x/y please' },
  { kind: 'run', text: 'skillgendev generate --route /campaigns/42/edit --name campaign-edit --xy --json' },
  { kind: 'result', status: 'needs', text: 'skill written from the code · exit 3 · the page showed a sign-in page' },
  {
    kind: 'agent',
    text: 'This page asks you to sign in before x/y can be measured. Open a browser window so you can sign in now?',
  },
  { kind: 'user', text: 'yes' },
  { kind: 'run', text: 'skillgendev login --url http://localhost:3000/login' },
  { kind: 'run', text: 'skillgendev generate --route /campaigns/42/edit --name campaign-edit --xy --overwrite' },
  { kind: 'result', status: 'written', text: 'analysis reused · code unchanged · x/y measured' },
];

const NEEDS = [
  { need: 'analysis', action: 'analyse', text: 'The agent reads the code itself' },
  { need: 'limit', action: 'ask', text: 'Wait for the AI’s limit to reset' },
  { need: 'url', action: 'ask', text: 'Ask for the dev address' },
  { need: 'server', action: 'ask', text: 'Ask to start the dev server' },
  { need: 'chromium', action: 'ask', text: 'Ask to download Chromium' },
  { need: 'probe', action: 'ask', text: 'Ask to install the probe extra' },
  { need: 'login', action: 'ask', text: 'Ask to open a sign-in window' },
  { need: 'open', action: 'ask', text: 'Ask which button opens the form' },
  { need: 'overwrite', action: 'ask', text: 'Ask before recreating a skill' },
];

function TurnLine({ turn }: { turn: Turn }): JSX.Element {
  if (turn.kind === 'user') {
    return (
      <div className="flex justify-end">
         <p className="max-w-[85%] bg-white/[0.07] px-3.5 py-2 text-[0.875rem] text-white/75">{turn.text}</p>
      </div>
    );
  }
  if (turn.kind === 'agent') {
    return (
      <div className="flex gap-3">
        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-galaxy-300" aria-hidden="true" />
         <p className="max-w-[90%] text-[0.95rem] leading-relaxed text-white/90">{turn.text}</p>
      </div>
    );
  }
  if (turn.kind === 'run') {
    return (
       <p className="break-all border-l border-white/15 pl-3 font-mono text-[0.75rem] text-white/50">
        <span className="text-galaxy-300">$ </span>
        {turn.text}
      </p>
    );
  }
  return (
     <p className="flex flex-wrap items-center gap-2 border-l border-white/15 pl-3 font-mono text-[0.75rem] text-white/40">
      <StatusChip status={turn.status} />
      {turn.text}
    </p>
  );
}

export default function HandoffSection(): JSX.Element {
  const [ref, isInView] = useInView<HTMLDivElement>({ threshold: 0.3 }, true);
  const isReduced = usePrefersReducedMotion();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (isReduced) {
      setShown(TURNS.length);
      return undefined;
    }
    if (!isInView || shown >= TURNS.length) return undefined;
    const timer = window.setTimeout(() => setShown((value) => value + 1), shown === 0 ? 300 : 1050);
    return () => window.clearTimeout(timer);
  }, [isInView, shown, isReduced]);

  const isHandingOff = shown >= 3 && shown < 7;
  const isDone = shown >= TURNS.length;

  return (
    <section id="agents" className="sg-section sg-tone-violet relative py-28 sm:py-36" aria-labelledby="agents-title">
      <div className="sg-shell">
        <SectionIntro
          index="05"
          tag="Built for agents"
          id="agents-title"
          title={
            <>
              It never waits at a prompt.
              <br className="hidden sm:block" /> It tells the agent what’s next.
            </>
          }
          lede="Every command is run by an AI agent, so none of them prompt. When a run needs something only you can give, it still does all it can from the code, exits with code 3, and hands over a next step. The agent asks you in chat and runs it again."
        />

        <div ref={ref} className="mt-16 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <Reveal>
            <Frame>
              <Window title="claude — ~/code/my-app" isSquare>
                <div className="flex min-h-[27rem] flex-col justify-end gap-4 p-5 sm:p-6">
                  {TURNS.slice(0, shown).map((turn, index) => (
                    <div key={index} className="animate-fade-up [animation-duration:0.5s]">
                      <TurnLine turn={turn} />
                    </div>
                  ))}
                  {!isDone && (
                    <span className="flex gap-1" aria-hidden="true">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white/40" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white/40 [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white/40 [animation-delay:300ms]" />
                    </span>
                  )}
                </div>
              </Window>
            </Frame>
          </Reveal>

          <Reveal delay={120} className="flex flex-col gap-6">
            <div
              className={clsx(
                 'sg-window border bg-[#0b0b0e] p-5 font-mono text-[0.75rem] leading-[1.7] transition-colors duration-700',
                isHandingOff ? 'border-galaxy-400/50' : 'border-white/[0.08]',
              )}
            >
               <p className="mb-2 text-white/30">result.next</p>
              <p className="text-white/50">{'{'}</p>
              {[
                ['action', '"ask"'],
                ['need', '"login"'],
                ['ask', '"Open a browser window so you can sign in now?"'],
                ['run', '"skillgendev login --url …/login"'],
                ['then', '"skillgendev generate … --xy --overwrite"'],
              ].map(([key, value]) => (
                <p key={key} className="break-words pl-4 sm:truncate">
                  <span className="text-galaxy-300">"{key}"</span>
                  <span className="text-white/40">: </span>
                   <span className={key === 'need' && isHandingOff ? 'text-white/90' : 'text-[#a5d6ff]'}>{value}</span>
                </p>
              ))}
              <p className="text-white/50">{'}'}</p>
            </div>

            <div>
               <p className="mb-3 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-white/30">
                Every need, one place
              </p>
              <ul className="grid grid-cols-1 border-t border-white/[0.07] sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                {NEEDS.map((item) => {
                  const isLive = item.need === 'login' && isHandingOff;
                  return (
                    <li
                      key={item.need}
                      className={clsx(
                        'flex items-baseline gap-3 border-b border-white/[0.07] py-2.5 pr-3 transition-colors duration-500',
                        isLive && 'bg-galaxy-500/[0.08]',
                      )}
                    >
                       <code className={clsx('w-[4.6rem] shrink-0 font-mono text-[0.75rem]', isLive ? 'text-galaxy-200' : 'text-white/60')}>
                        {item.need}
                      </code>
                       <span className="text-[0.875rem] text-white/40">{item.text}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
