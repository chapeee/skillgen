import React from 'react';
import Link from '@docusaurus/Link';
import BrowserOnly from '@docusaurus/BrowserOnly';
import ParticleField from './particles/ParticleField';
import { BrandLogo, Button, CommandLine } from './ui';
import { ArrowBarIcon, GitHubIcon } from './icons';
import { GITSMITH_NPM_URL, REPOSITORY_URL } from './constants';

/** The page ends where it began: the same swell, the same glass. */
export function FinalCallToAction(): JSX.Element {
  return (
    <section className="relative px-3 pb-3 pt-10 sm:px-4 sm:pb-4 lg:px-5 lg:pb-5" aria-labelledby="cta-title">
      <div
        className="sg-dark relative isolate overflow-hidden rounded-[16px] bg-[#0a0a0c] border border-white/[0.16] sm:rounded-[18px]"
        style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.08), 0 40px 120px -30px rgba(0,0,0,0.85)' }}
      >
        <BrowserOnly fallback={<div className="absolute inset-0 bg-[#0a0a0c]" />}>
          {() => <ParticleField className="absolute inset-0 -z-10 h-full w-full" />}
        </BrowserOnly>
        <div className="sg-hero-light sg-closing-light pointer-events-none absolute inset-0 -z-10" aria-hidden="true" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              'radial-gradient(ellipse 70% 60% at 50% 55%, rgba(8,8,10,0.35), rgba(8,8,10,0.8) 75%), linear-gradient(to bottom, rgba(8,8,10,0.6), rgba(8,8,10,0) 30%)',
          }}
        />
        <div className="flex min-h-[78svh] flex-col items-center justify-center px-5 py-24 text-center sm:min-h-[44rem]">
           <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-white/40">Start with one page</p>
           <h2 id="cta-title" className="sg-hero-title mt-5 max-w-4xl text-balance text-[2.5rem] font-semibold leading-[1.08] tracking-[-0.045em] text-white/95 sm:text-[3.1rem] lg:text-[3.8rem]">
            Give every page of your app a skill.
          </h2>
           <p className="mt-5 max-w-lg text-[1rem] leading-[1.6] text-white/50">
            Point skillgendev at your repository. Your agent does the rest, and asks you only what it must.
          </p>
          <div className="mt-10 w-full max-w-xl">
            <CommandLine command="skillgendev generate --route /campaigns/new --name new-campaign" className="bg-black/60 backdrop-blur-md" />
          </div>
           <div className="mt-8 flex w-full max-w-md sm:w-auto">
             <Button to="/docs/" variant="secondary" className="h-12 flex-1 whitespace-nowrap px-4 sm:flex-none sm:px-7">
              Read the Docs
            </Button>
             <Button to="/docs/getting-started/quick-start/" className="h-12 flex-1 whitespace-nowrap px-4 sm:flex-none sm:px-7">
              Start Generating
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

const FOOTER_COLUMNS = [
  {
    title: 'Start',
    links: [
      { label: 'Overview', to: '/docs/' },
      { label: 'Installation', to: '/docs/getting-started/installation/' },
      { label: 'Quick start', to: '/docs/getting-started/quick-start/' },
      { label: 'Using skills', to: '/docs/getting-started/using-skills/' },
    ],
  },
  {
    title: 'Learn',
    links: [
      { label: 'How it works', to: '/docs/concepts/how-it-works/' },
      { label: 'Command reference', to: '/docs/reference/cli/' },
      { label: 'Architecture', to: '/docs/architecture/overview/' },
      { label: 'Troubleshooting', to: '/docs/troubleshooting/' },
    ],
  },
  {
    title: 'Project',
    links: [
      { label: 'GitHub', href: REPOSITORY_URL },
      { label: 'Issues', href: `${REPOSITORY_URL}/issues` },
      { label: 'Contributing', to: '/docs/contributing/' },
      { label: 'Gitsmith', href: GITSMITH_NPM_URL },
    ],
  },
];

export function LandingFooter(): JSX.Element {
  return (
    <footer className="sg-landing-footer relative isolate overflow-hidden pb-12 pt-20">
      {/* A hairline that glows at its centre opens the footer. */}
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-galaxy-300/50 to-transparent" />

      <div className="sg-shell relative grid gap-12 md:grid-cols-[1.2fr_2fr]">
        <div>
           <Link to="/" className="inline-flex items-center gap-2.5 text-[1.1rem] font-medium uppercase tracking-[0.12em] text-white/95">
            <BrandLogo className="h-9 w-9" />
            .skillgendev
          </Link>
           <p className="mt-4 max-w-xs text-[0.95rem] leading-relaxed text-white/50">
            A framework- and domain-agnostic compiler from application code to Agent Skills.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <a
              href={REPOSITORY_URL}
              className="inline-flex items-center gap-2 border border-white/[0.16] bg-white/[0.04] px-3 py-2 text-[0.85rem] text-white/60 backdrop-blur-sm transition-colors hover:border-white/40 hover:text-white/90"
            >
              <GitHubIcon className="h-4 w-4" /> chapeee/skillprinter
              <ArrowBarIcon className="h-3.5 w-3.5" />
            </a>
            <span className="inline-flex items-center gap-2 border border-galaxy-400/30 bg-galaxy-500/10 px-3 py-2 font-mono text-[0.7rem] uppercase tracking-[0.13em] text-galaxy-100">
              <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-galaxy-300 opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-galaxy-300" />
              </span>
              v0.1.0 · pre-alpha
            </span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
          {FOOTER_COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-white/40">{column.title}</p>
              <ul className="mt-3.5 space-y-2">
                {column.links.map((link) => (
                  <li key={link.label}>
                    {'to' in link && link.to ? (
                      <Link
                        to={link.to}
                        className="text-[0.9rem] text-white/60 underline-offset-4 transition-colors hover:text-white/90 hover:underline hover:decoration-galaxy-300"
                      >
                        {link.label}
                      </Link>
                    ) : (
                      <a
                        href={link.href}
                        className="text-[0.9rem] text-white/60 underline-offset-4 transition-colors hover:text-white/90 hover:underline hover:decoration-galaxy-300"
                      >
                        {link.label}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="sg-shell relative mt-14 flex flex-col gap-2 border-t border-white/[0.1] pt-5 font-mono text-[0.68rem] uppercase tracking-[0.13em] text-white/40 sm:flex-row sm:justify-between">
        <span>© {new Date().getFullYear()} skillgendev contributors · Apache 2.0</span>
        <span>pip install skillgendev</span>
      </div>
    </footer>
  );
}
