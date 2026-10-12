import React, { useState } from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import { Reveal, SectionHeading, SectionTag } from './ui';

const QUESTIONS = [
  {
    question: 'Which AIs can use the skills?',
    answer:
      'Any AI that accepts Agent Skills and has a browser: Claude, Cowork, ChatGPT and others. Each skill carries four fill methods, so it works whether or not the browser can run JavaScript in the page.',
  },
  {
    question: 'Does it need an MCP server, an extension or an API key where skills are used?',
    answer:
      'No. Skills use the AI’s built-in browser and nothing installed. The library never depends on or mentions MCP servers.',
  },
  {
    question: 'Which frameworks are supported?',
    answer:
      'Any web app whose forms render as HTML. Frameworks only matter for finding routes: folder conventions and ast-grep hint packs cover Next.js, Nuxt, SvelteKit, Astro, React Router, Express, Flask, Django, Laravel, Rails, Spring, ASP.NET and Phoenix, and Claude Code reads the code graph for anything else.',
  },
  {
    question: 'Do I need a running copy of my app?',
    answer:
      'No. Generation reads code only by default. A dev or staging copy is needed only for --xy, which adds field positions and a layout check. It never removes or changes what the code gave.',
  },
  {
    question: 'Is it safe to point the probe at my app?',
    answer:
      'Only at dev or staging. The probe refuses an environment marked production, intercepts and cancels write requests, never submits, and never clicks things like Save, Delete or Sign out.',
  },
  {
    question: 'Will regenerating erase my edits?',
    answer:
      'Not the ones between the skillgendev:user markers in SKILL.md; they survive every regeneration. And a regenerated skill only replaces the old one when it passes every check.',
  },
  {
    question: 'How much does it save at fill time?',
    answer:
      'The design spec models a 40-field form at about 8 tool calls with a skill against about 138 with computer use, roughly 25× fewer input tokens. That is a model from the spec, not a published measurement yet.',
  },
  {
    question: 'Is it on PyPI?',
    answer: 'Yes. Install it with uv tool install "skillgendev[probe]", pipx or pip. It is pre-alpha, so interfaces may still change.',
  },
];

export default function FaqSection(): JSX.Element {
  const [open, setOpen] = useState(0);

  return (
    <section id="faq" className="sg-section sg-tone-violet relative py-28 sm:py-36" aria-labelledby="faq-title">
      <div className="sg-shell grid gap-12 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
        <Reveal className="lg:sticky lg:top-28 lg:self-start">
          <SectionTag index="06">FAQ</SectionTag>
          <SectionHeading id="faq-title" className="mt-6">
            Questions,
            <br /> answered.
          </SectionHeading>
           <p className="mt-6 max-w-xs text-[0.95rem] leading-relaxed text-white/40">
            More in the <Link to="/docs/faq/" className="text-white/80 underline decoration-white/30 underline-offset-4 hover:text-white hover:decoration-white">docs FAQ</Link> and{' '}
            <Link to="/docs/troubleshooting/" className="text-white/80 underline decoration-white/30 underline-offset-4 hover:text-white hover:decoration-white">troubleshooting</Link>.
          </p>
        </Reveal>

        <Reveal delay={100}>
          <ul className="border-t border-white/[0.08]">
            {QUESTIONS.map((item, index) => {
              const isOpen = index === open;
              const panelId = `faq-panel-${index}`;
              return (
                <li key={item.question} className="sg-faq-item border-b border-white/[0.08]" data-open={isOpen}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => setOpen(isOpen ? -1 : index)}
                   className="flex w-full items-center justify-between gap-6 px-4 py-5 text-left sm:px-5"
                  >
                    <span className={clsx('text-[1.05rem] font-medium tracking-[-0.01em] transition-colors sm:text-[1.1rem]', isOpen ? 'text-white/90' : 'text-white/60 hover:text-white/90')}>
                      {item.question}
                    </span>
                    <span className="relative h-3 w-3 shrink-0" aria-hidden="true">
                      <span className="absolute left-0 top-1/2 h-px w-3 -translate-y-1/2 bg-white/60" />
                      <span className={clsx('absolute left-1/2 top-0 h-3 w-px -translate-x-1/2 bg-white/60 transition-transform duration-300', isOpen && 'scale-y-0')} />
                    </span>
                  </button>
                  <div
                    id={panelId}
                    aria-hidden={!isOpen}
                    className={clsx('sg-faq-panel grid', isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}
                  >
                   <p className="overflow-hidden pl-4 pr-10 text-[0.95rem] leading-[1.7] text-white/60 sm:pl-5">
                     <span className="block pb-5">{item.answer}</span>
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}
