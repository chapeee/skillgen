import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import BrowserOnly from '@docusaurus/BrowserOnly';
import DotMorph from './dots/DotMorph';
import { Button, Frame, SectionIntro } from './ui';
import { ArrowRightIcon } from './icons';

const STEPS = [
  {
    title: 'Find routes',
    body: 'Folder conventions, ast-grep router packs and Graphify’s route nodes find the pages. When none of them do, Claude Code reads the code graph’s likely router files. You can always add one by hand.',
    writes: '.skillgendev/routes.json',
    detail: 'Next.js · Nuxt · SvelteKit · Astro · React Router · Express · Flask · Django · Rails · Laravel · Spring · ASP.NET · Phoenix',
  },
  {
    title: 'Slice the page',
    body: 'From the page’s own component, Graphify follows imports three hops deep and keeps only the files that build it: at most 40 files, about 60k tokens. Sibling pages stay out.',
    writes: '.skillgendev/pages/<skill>/slice.json',
    detail: 'depth 3 · max 40 files · ~60k tokens',
  },
  {
    title: 'Read the code',
    body: 'Claude Code reads the slice with read-only tools and answers in a JSON schema: what every field means, its options, rules, conditions, and the steps or dialogs it hides behind. The only step that spends tokens.',
    writes: '.skillgendev/pages/<skill>/analysis.json',
    detail: 'Read · Grep · Glob · --json-schema',
  },
  {
    title: 'Weigh every fact',
    body: 'Code, the optional probe and your answers merge into one page model. Agreeing sources combine as 1 − (1 − a)(1 − b); anything under 0.7 becomes a question for you instead of an instruction.',
    writes: '.skillgendev/pages/<skill>/page.json',
    detail: 'stated in code 0.85 · seen on page 0.90 · deduced 0.60',
  },
  {
    title: 'Write the skill',
    body: 'Templates turn the model into SKILL.md, a one-call fill script, locators and plain steps. Spec checks and a secret scan run before anything is written; a failing skill never replaces a good one.',
    writes: 'skills/<skill>/SKILL.md',
    detail: 'SKILL.md · fill.md · fill.js · locators.md · manual-steps.md · evals.json',
  },
];

function StoryVisual({ active }: { active: number }): JSX.Element {
  const step = STEPS[active];
  return (
    <Frame className="h-full w-full">
      <div className="sg-window relative h-full w-full overflow-hidden border border-white/[0.08]">
        <div className="sg-grid-bg pointer-events-none absolute inset-0 opacity-50" aria-hidden="true" />
         <div className="absolute left-4 right-4 top-4 flex items-center justify-between font-mono text-[0.68rem] uppercase tracking-[0.16em] text-white/40">
          <span>
            <span className="text-galaxy-300">{String(active + 1).padStart(2, '0')}</span> / 05 · {step.title}
          </span>
          <span className="hidden sm:inline">skillgendev generate</span>
        </div>
        <BrowserOnly fallback={<div className="absolute inset-0" />}>
          {() => (
            <DotMorph
              shape={active}
              className="absolute inset-x-0 bottom-14 top-10 h-[calc(100%-6rem)] w-full"
              label={`Illustration of the ${step.title.toLowerCase()} step`}
            />
          )}
        </BrowserOnly>
        <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-4 border-t border-white/[0.06] bg-black/40 px-4 py-3 backdrop-blur-sm">
           <div className="min-w-0 font-mono text-[0.75rem]">
             <span className="text-white/30">writes </span>
            <span className="truncate text-galaxy-200">{step.writes}</span>
          </div>
          <div className="flex shrink-0 gap-1" aria-hidden="true">
            {STEPS.map((item, index) => (
              <span
                key={item.title}
                className={clsx(
                  'h-1 transition-all duration-500',
                  index === active ? 'w-6 bg-galaxy-300' : index < active ? 'w-2 bg-white/40' : 'w-2 bg-white/15',
                )}
              />
            ))}
          </div>
        </div>
      </div>
    </Frame>
  );
}

export default function StorySection(): JSX.Element {
  const [active, setActive] = useState(0);
  const stepRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.index));
        });
      },
      { rootMargin: '-48% 0px -48% 0px', threshold: 0 },
    );
    stepRefs.current.forEach((node) => node && observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <section id="how-it-works" className="sg-dark sg-section sg-band sg-band-dark sg-tone-violet relative py-28 sm:py-36" aria-labelledby="story-title">
      <div className="sg-shell">
        <SectionIntro
          index="02"
          tag="How it works"
          id="story-title"
          title={
            <>
              From a repository to a skill,
              <br className="hidden sm:block" /> one page at a time.
            </>
          }
          lede="Claude Code does the understanding; deterministic tools do the measuring. Five steps run per route, and only one of them spends model tokens."
        />

        <div className="mt-16 grid gap-10 lg:mt-20 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16">
          <div className="sg-story-stage sticky top-0 z-10 -mx-5 h-[calc(44svh+4.5rem)] self-start px-5 pb-3 pt-[4.5rem] sm:-mx-8 sm:px-8 lg:order-2 lg:top-[12svh] lg:mx-0 lg:h-[76svh] lg:p-0">
            <StoryVisual active={active} />
          </div>

          <ol className="relative lg:order-1">
            <span aria-hidden="true" className="absolute bottom-0 left-[0.6rem] top-0 w-px bg-white/[0.07]" />
            {STEPS.map((step, index) => {
              const isActive = index === active;
              return (
                <li
                  key={step.title}
                  ref={(node) => {
                    stepRefs.current[index] = node;
                  }}
                  data-index={index}
                  className="relative flex min-h-[46svh] flex-col justify-center py-10 pl-10 lg:min-h-[62svh]"
                >
                  <span
                    aria-hidden="true"
                    className={clsx(
                      'absolute left-[0.6rem] top-1/2 h-16 w-px -translate-y-1/2 transition-colors duration-500',
                      isActive ? 'bg-galaxy-300 shadow-[0_0_12px_rgba(140,166,255,0.9)]' : 'bg-transparent',
                    )}
                  />
                  <span
                    className={clsx(
                       'font-mono text-[0.75rem] tracking-[0.14em] transition-colors duration-500',
                      isActive ? 'text-galaxy-300' : 'text-white/25',
                    )}
                  >
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <h3
                    className={clsx(
                       'mt-3 text-[1.45rem] font-medium tracking-[-0.03em] transition-colors duration-500 sm:text-[1.7rem]',
                       isActive ? 'text-white/90' : 'text-white/40',
                    )}
                  >
                    {step.title}
                  </h3>
                  <p
                    className={clsx(
                       'mt-4 max-w-md text-[1rem] leading-[1.65] transition-colors duration-500',
                       isActive ? 'text-white/60' : 'text-white/40',
                    )}
                  >
                    {step.body}
                  </p>
                  <p
                    className={clsx(
                       'mt-5 max-w-md font-mono text-[0.75rem] leading-relaxed transition-colors duration-500',
                       isActive ? 'text-white/40' : 'text-white/30',
                    )}
                  >
                    {step.detail}
                  </p>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4 border-t border-white/[0.06] pt-8">
           <p className="max-w-xl text-[0.95rem] leading-relaxed text-white/40">
            Optional: <code className="font-mono text-white/80">--xy</code> opens the page on a dev copy and
            measures where each field sits. It only ever adds; nothing is submitted.
          </p>
          <Button to="/docs/concepts/how-it-works/" variant="ghost" className="h-10">
            The pipeline in depth
            <ArrowRightIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Button>
        </div>
      </div>
    </section>
  );
}
