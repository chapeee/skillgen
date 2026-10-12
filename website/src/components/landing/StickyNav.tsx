import React, { useEffect, useState } from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import { ArrowBarIcon, GitHubIcon } from './icons';
import { REPOSITORY_URL } from './constants';
import { BrandLogo } from './ui';

const LINKS = [
  { label: 'How it works', id: 'how-it-works' },
  { label: 'Output', id: 'anatomy' },
  { label: 'Fill', id: 'fill' },
  { label: 'Agents', id: 'agents' },
  { label: 'FAQ', id: 'faq' },
];

/** Appears once the hero's own nav has scrolled away, and tracks the section in view. */
export default function StickyNav(): JSX.Element {
  const [isShown, setIsShown] = useState(false);
  const [current, setCurrent] = useState('');

  useEffect(() => {
    const hero = document.getElementById('hero');
    if (!hero) return undefined;
    const heroObserver = new IntersectionObserver(([entry]) => setIsShown(!entry.isIntersecting), {
      rootMargin: '-80px 0px 0px 0px',
    });
    heroObserver.observe(hero);

    const sectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setCurrent(entry.target.id);
        });
      },
      { rootMargin: '-45% 0px -50% 0px' },
    );
    LINKS.forEach((link) => {
      const node = document.getElementById(link.id);
      if (node) sectionObserver.observe(node);
    });
    return () => {
      heroObserver.disconnect();
      sectionObserver.disconnect();
    };
  }, []);

  return (
    <div
      aria-hidden={!isShown}
      className={clsx(
        'sg-sticky-nav fixed inset-x-0 top-0 z-50 flex justify-center px-3 pt-3',
        isShown ? 'visible translate-y-0 opacity-100' : 'invisible pointer-events-none -translate-y-4 opacity-0',
      )}
    >
      <nav
        aria-label="Sections"
         className="sg-dark sg-nav-surface flex h-11 w-full max-w-[64rem] items-center justify-between gap-4 border border-white/[0.1] bg-[#0a0a0c]/75 pl-4 pr-1.5 backdrop-blur-xl"
      >
        <a href="#hero" className="flex shrink-0 items-center gap-2 text-[0.875rem] font-medium uppercase tracking-[0.12em] text-white/95">
          <BrandLogo className="h-6 w-6" />
          .skillgendev
        </a>
        <ul className="hidden items-center gap-1 lg:flex">
          {LINKS.map((link) => (
            <li key={link.id}>
              <a
                href={`#${link.id}`}
                aria-current={current === link.id ? 'location' : undefined}
                className={clsx(
                   'sg-nav-link px-2.5 py-1.5 text-[0.8rem]',
                   current === link.id ? 'text-white/90' : 'text-white/40 hover:text-white/75',
                )}
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-1">
           <a href={REPOSITORY_URL} aria-label="GitHub repository" className="hidden h-9 w-9 items-center justify-center text-white/40 hover:text-white/90 sm:flex">
            <GitHubIcon className="h-4 w-4" />
          </a>
           <Link to="/docs/" className="hidden h-9 items-center px-3 text-[0.84rem] text-white/60 hover:text-white/90 sm:flex">
            Docs
          </Link>
          <Link
            to="/docs/getting-started/quick-start/"
             className="sg-button sg-button--primary group flex h-9 items-center gap-2 bg-white px-3.5 text-[0.84rem] text-[#0a0a0c] hover:bg-white/85"
          >
            Get started
            <ArrowBarIcon className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </nav>
    </div>
  );
}
