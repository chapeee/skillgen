import React, { useEffect, useRef, useState } from 'react';
import Link from '@docusaurus/Link';
import BrowserOnly from '@docusaurus/BrowserOnly';
import ParticleField from './particles/ParticleField';
import { ArrowBarIcon, GitHubIcon, MenuIcon } from './icons';
import { REPOSITORY_URL } from './constants';
import { BrandLogo } from './ui';

const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Output', href: '#anatomy' },
  { label: 'Fill', href: '#fill' },
  { label: 'Docs', to: '/docs/' },
];

// Supported stacks, shown as plain wordmarks. They describe where route
// discovery works today (see the docs), not who uses skillgendev.
const STACKS = [
  { name: 'Next.js', className: 'font-semibold tracking-[-0.04em]' },
  { name: 'React Router', className: 'font-medium tracking-[-0.02em]' },
  { name: 'Flask', className: 'font-serif italic tracking-[-0.01em]' },
  { name: 'django', className: 'font-bold tracking-[-0.05em]' },
  { name: 'Laravel', className: 'font-semibold tracking-[-0.02em]' },
  { name: 'Rails', className: 'font-bold italic tracking-[-0.02em]' },
];

function HeroNav(): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
        document.getElementById('hero-menu-toggle')?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen]);

  return (
    <nav aria-label="Primary" className="sg-hero-nav relative z-20 flex items-center justify-between">
      <Link
        to="/"
        className="flex items-center gap-2.5 text-[1rem] font-medium uppercase tracking-[0.12em] text-white/95 sm:text-[1.1rem]"
      >
        <BrandLogo className="h-8 w-8 sm:h-9 sm:w-9" />
        .skillgendev
      </Link>

      <div className="hidden items-center gap-8 md:flex">
        <ul className="flex items-center gap-6 lg:gap-7">
          {NAV_LINKS.map((item) => (
            <li key={item.label}>
              {item.to ? (
                <Link
                  to={item.to}
                  className="text-[0.875rem] text-white/60 transition-colors duration-300 hover:text-white/90"
                >
                  {item.label}
                </Link>
              ) : (
                <a
                  href={item.href}
                  className="text-[0.875rem] text-white/60 transition-colors duration-300 hover:text-white/90"
                >
                  {item.label}
                </a>
              )}
            </li>
          ))}
        </ul>
        <Link
          to="/docs/getting-started/quick-start/"
          className="group inline-flex items-center gap-2.5 text-[0.875rem] font-medium text-white/90"
        >
          Get started
          <ArrowBarIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5" />
        </Link>
      </div>

      <button
        id="hero-menu-toggle"
        type="button"
        className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/15 bg-white/5 text-white md:hidden"
        aria-expanded={isOpen}
        aria-controls="hero-mobile-menu"
        aria-label={isOpen ? 'Close menu' : 'Open menu'}
        onClick={() => setIsOpen((value) => !value)}
      >
        <MenuIcon isOpen={isOpen} className="h-5 w-5" />
      </button>

      {isOpen && (
        <div
          id="hero-mobile-menu"
          className="sg-mobile-menu absolute right-0 top-12 w-56 rounded-xl border border-white/10 bg-[#0c0c10]/95 p-2 shadow-2xl backdrop-blur-xl md:hidden"
        >
          {NAV_LINKS.map((item) =>
            item.to ? (
              <Link
                key={item.label}
                to={item.to}
                 className="block rounded-lg px-3 py-2.5 text-[0.875rem] text-white/60 hover:bg-white/5 hover:text-white/90"
              >
                {item.label}
              </Link>
            ) : (
              <a
                key={item.label}
                href={item.href}
                onClick={() => setIsOpen(false)}
                 className="block rounded-lg px-3 py-2.5 text-[0.875rem] text-white/60 hover:bg-white/5 hover:text-white/90"
              >
                {item.label}
              </a>
            ),
          )}
          <a
            href={REPOSITORY_URL}
             className="mt-1 flex items-center gap-2 rounded-lg border-t border-white/10 px-3 py-2.5 text-[0.875rem] text-white/60 hover:text-white/90"
          >
            <GitHubIcon className="h-4 w-4" /> GitHub
          </a>
        </div>
      )}
    </nav>
  );
}

export default function Hero(): JSX.Element {
  const sectionRef = useRef<HTMLElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  return (
    <section
      id="hero"
      ref={sectionRef}
      className="relative isolate overflow-hidden bg-[var(--sg-landing-bg)]"
      aria-labelledby="hero-title"
    >
      <div className="relative z-10 flex min-h-[100svh] items-stretch justify-center p-3 sm:p-4 lg:p-5">
        <div
          ref={panelRef}
          className="sg-dark relative isolate flex bg-[#0a0a0c] min-h-[calc(100svh-1.5rem)] w-full flex-col overflow-hidden rounded-[16px] border border-white/[0.16] px-5 pb-6 pt-5 sm:min-h-[calc(100svh-2rem)] sm:rounded-[18px] sm:px-10 sm:pb-9 sm:pt-7 lg:min-h-[calc(100svh-2.5rem)] lg:px-14 lg:pb-11 lg:pt-9"
          style={{
            boxShadow:
              'inset 0 1px 0 rgba(255,255,255,0.08), inset 0 0 0 1px rgba(255,255,255,0.03), 0 40px 90px -40px rgba(10,14,40,0.45)',
          }}
        >
          {/* The binary swell lives inside the dark panel, a screen on a white page. */}
          <BrowserOnly fallback={<div className="absolute inset-0" />}>
            {() => <ParticleField className="absolute inset-0 -z-10 h-full w-full" />}
          </BrowserOnly>
          <div className="sg-hero-light pointer-events-none absolute inset-0 -z-10" aria-hidden="true" />
          {/* Readability: the field stays vivid in the middle and calms under the text. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'linear-gradient(to bottom, rgba(8,8,10,0.5) 0%, rgba(8,8,10,0) 16%), linear-gradient(to top, rgba(8,8,10,0.88) 0%, rgba(8,8,10,0.45) 20%, rgba(8,8,10,0) 42%), radial-gradient(ellipse 55% 40% at 16% 80%, rgba(8,8,10,0.5), rgba(8,8,10,0) 70%)',
            }}
          />

          <HeroNav />

          <div className="relative z-10 mt-auto">
            <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-[46rem]">
                <h1
                  id="hero-title"
                   className="sg-hero-title animate-fade-up text-balance text-[2.25rem] font-semibold leading-[1.08] tracking-[-0.045em] text-white/95 [animation-delay:150ms] sm:text-wrap sm:text-[3rem] lg:text-[3.5rem] xl:text-[4rem]"
                >
                  Where App Code and
                  <br className="hidden sm:block" /> Agent Skills Align
                </h1>
                <p className="mt-5 max-w-[29rem] animate-fade-up text-pretty text-[1rem] leading-[1.65] text-white/60 [animation-delay:300ms] sm:text-[1.06rem]">
                  skillgendev reads your app’s code and writes one Agent Skill per page: like a reusable
                  memory of how your app works, ready whenever an AI needs it, so every task takes
                  fewer tokens.
                </p>
              </div>

              <div className="flex w-full animate-fade-up [animation-delay:450ms] sm:w-auto">
                <Link
                  to="/docs/"
                   className="sg-button sg-button--secondary flex h-12 flex-1 items-center justify-center whitespace-nowrap bg-white/[0.09] px-4 text-[0.92rem] text-white/90 backdrop-blur-md hover:bg-white/[0.15] sm:px-7 sm:flex-none"
                >
                  Read the Docs
                </Link>
                <Link
                  to="/docs/getting-started/quick-start/"
                   className="sg-button sg-button--primary flex h-12 flex-1 items-center justify-center whitespace-nowrap bg-white px-4 text-[0.92rem] text-[#0a0a0c] hover:bg-white/85 sm:px-7 sm:flex-none"
                >
                  Start Generating
                </Link>
              </div>
            </div>

            <div className="mt-10 animate-fade-up border-t border-white/[0.08] pt-5 [animation-delay:600ms] sm:mt-12">
               <p className="mb-3.5 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-white/30">
                Finds routes in
              </p>
              <ul
                className="grid grid-cols-3 items-center gap-x-6 gap-y-4 sm:flex sm:justify-between"
                aria-label="Stacks whose routes skillgendev discovers"
              >
                {STACKS.map((stack) => (
                  <li
                    key={stack.name}
                     className={`whitespace-nowrap text-center text-[1rem] text-white/40 transition-colors duration-300 hover:text-white/75 sm:text-[1.1rem] ${stack.className}`}
                  >
                    {stack.name}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
