import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import { CheckIcon, CopyIcon } from './icons';

/** The logo mark; decorative, because the wordmark beside it names the link. */
export function BrandLogo({ className }: { className?: string }): JSX.Element {
  const src = useBaseUrl('/img/skillgen-logo.png');
  // A white tile keeps the dark mark legible on the dark hero and nav.
  return (
    <span aria-hidden="true" className={clsx('relative inline-block shrink-0 rounded-[22%] bg-[#fff] ring-1 ring-black/10', className)}>
      <img src={src} alt="" width={36} height={36} className="absolute left-[8%] top-[8%] h-[84%] w-[84%] max-w-none select-none object-contain" draggable={false} />
    </span>
  );
}

/*
 * The landing page's shared vocabulary, taken from the hero: square buttons,
 * hairline borders, light tightly tracked headings, mono labels, and the
 * viewfinder corners that frame every product visual.
 */

export function useInView<T extends Element>(
  options: IntersectionObserverInit = { threshold: 0.25 },
  once = false,
): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [isInView, setIsInView] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      setIsInView(entry.isIntersecting);
      if (entry.isIntersecting && once) observer.disconnect();
    }, options);
    observer.observe(node);
    return () => observer.disconnect();
    // Options are static per call site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [ref, isInView];
}

export function usePrefersReducedMotion(): boolean {
  const [isReduced, setIsReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setIsReduced(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return isReduced;
}

/** Fades its children in once they scroll into view. */
export function Reveal({
  children,
  className,
  delay = 0,
  as: Tag = 'div',
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  as?: 'div' | 'li' | 'section' | 'article' | 'header';
}): JSX.Element {
  const [ref, isVisible] = useInView<HTMLElement>({ rootMargin: '0px 0px -8% 0px', threshold: 0.08 }, true);
  return React.createElement(
    Tag,
    {
      ref,
      className: clsx('sg-reveal', isVisible && 'is-visible', className),
      style: { '--sg-delay': `${delay}ms` } as React.CSSProperties,
    },
    children,
  );
}

export function SectionTag({ index, children }: { index: string; children: React.ReactNode }): JSX.Element {
  return (
    <span className="sg-section-tag inline-flex items-center gap-2.5 border px-3 py-1.5 font-mono text-[0.68rem] font-medium uppercase tracking-[0.16em]">
      <span className="text-galaxy-300">{index}</span>
      <span className="h-2.5 w-px bg-white/15" aria-hidden="true" />
      {children}
    </span>
  );
}

export function SectionHeading({
  id,
  children,
  className,
}: {
  id?: string;
  children: React.ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <h2
      id={id}
      className={clsx(
        'sg-section-heading text-balance text-[2.15rem] font-semibold leading-[1.08] tracking-[-0.04em] text-white/95 sm:text-[2.75rem] lg:text-[3.35rem]',
        className,
      )}
    >
      {children}
    </h2>
  );
}

export function Lede({ children, className }: { children: React.ReactNode; className?: string }): JSX.Element {
  return (
    <p className={clsx('sg-lede max-w-2xl text-pretty text-[0.98rem] leading-[1.65] text-white/60 sm:text-[1.08rem]', className)}>
      {children}
    </p>
  );
}

/** Section opening: tag, heading, lede and an optional action on the right. */
export function SectionIntro({
  index,
  tag,
  title,
  lede,
  id,
  aside,
}: {
  index: string;
  tag: string;
  title: React.ReactNode;
  lede?: React.ReactNode;
  id: string;
  aside?: React.ReactNode;
}): JSX.Element {
  return (
    <Reveal as="header" className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="flex max-w-3xl flex-col gap-5">
        <div>
          <SectionTag index={index}>{tag}</SectionTag>
        </div>
        <SectionHeading id={id}>{title}</SectionHeading>
        {lede && <Lede>{lede}</Lede>}
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </Reveal>
  );
}

/** Viewfinder corners: the frame every product visual sits in. */
export function Frame({
  children,
  className,
  tone = 'default',
}: {
  children: React.ReactNode;
  className?: string;
  tone?: 'default' | 'accent';
}): JSX.Element {
  const line = tone === 'accent' ? 'border-galaxy-300/70' : 'border-white/30';
  return (
    <div className={clsx('sg-frame relative', className)}>
      <span aria-hidden="true" className={clsx('pointer-events-none absolute -left-px -top-px h-3.5 w-3.5 border-l border-t', line)} />
      <span aria-hidden="true" className={clsx('pointer-events-none absolute -right-px -top-px h-3.5 w-3.5 border-r border-t', line)} />
      <span aria-hidden="true" className={clsx('pointer-events-none absolute -bottom-px -left-px h-3.5 w-3.5 border-b border-l', line)} />
      <span aria-hidden="true" className={clsx('pointer-events-none absolute -bottom-px -right-px h-3.5 w-3.5 border-b border-r', line)} />
      {children}
    </div>
  );
}

/** A full-width hairline with crosshair ticks at the content edges. */
export function Divider({ label }: { label?: string }): JSX.Element {
  return (
    <div className="sg-divider relative" aria-hidden="true">
      <div className="sg-divider-line h-px w-full" />
      <div className="sg-shell pointer-events-none absolute inset-x-0 -top-[5px] flex justify-between">
        <span className="relative block h-[11px] w-[11px]">
          <span className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-white/25" />
          <span className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-white/25" />
        </span>
        {label && (
          <span className="sg-divider-label -mt-[3px] px-3 font-mono text-[0.72rem] uppercase tracking-[0.2em] text-white/40">
            {label}
          </span>
        )}
        <span className="relative block h-[11px] w-[11px]">
          <span className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-white/25" />
          <span className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-white/25" />
        </span>
      </div>
    </div>
  );
}

type ButtonProps = {
  children: React.ReactNode;
  to?: string;
  href?: string;
  variant?: 'primary' | 'secondary' | 'ghost';
  className?: string;
};

/** Square buttons, exactly like the hero's call to action. */
export function Button({ children, to, href, variant = 'primary', className }: ButtonProps): JSX.Element {
  const classes = clsx(
    'sg-button group inline-flex h-11 items-center justify-center gap-2.5 px-5 text-[0.92rem]',
    `sg-button--${variant}`,
    variant === 'primary' && 'bg-white text-[#0a0a0c] hover:bg-white/85',
     variant === 'secondary' && 'bg-white/[0.08] text-white/90 backdrop-blur-md hover:bg-white/[0.14]',
    variant === 'ghost' && 'border border-white/[0.12] text-white/70 hover:border-white/30 hover:text-white/90',
    className,
  );
  if (to) {
    return (
      <Link to={to} className={classes}>
        {children}
      </Link>
    );
  }
  return (
    <a href={href} className={classes}>
      {children}
    </a>
  );
}

export function CopyButton({ text, className }: { text: string; className?: string }): JSX.Element {
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (!isCopied) return undefined;
    const timer = window.setTimeout(() => setIsCopied(false), 1600);
    return () => window.clearTimeout(timer);
  }, [isCopied]);

  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(text).then(
          () => setIsCopied(true),
          () => undefined,
        );
      }}
      className={clsx(
        'sg-copy inline-flex h-8 w-8 shrink-0 items-center justify-center text-white/40 transition-colors hover:text-white/90',
        className,
      )}
      aria-label={isCopied ? 'Copied' : `Copy: ${text}`}
    >
      {isCopied ? <CheckIcon className="h-4 w-4 text-galaxy-300" /> : <CopyIcon className="h-4 w-4" />}
    </button>
  );
}

/** One shell command with a copy button. */
export function CommandLine({ command, className }: { command: string; className?: string }): JSX.Element {
  return (
    <div
      className={clsx(
        'sg-command flex items-center gap-3 border border-white/[0.09] py-1.5 pl-4 pr-1.5 font-mono text-[0.84rem] text-white/70',
        className,
      )}
    >
      <span className="select-none text-galaxy-300">$</span>
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">{command}</code>
      <CopyButton text={command} />
    </div>
  );
}

/** A hairline window: terminal, editor or browser chrome. */
export function Window({
  title,
  children,
  className,
  actions,
  kind = 'dots',
  isSquare = false,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
  kind?: 'dots' | 'browser';
  isSquare?: boolean;
}): JSX.Element {
  return (
    <div
      className={clsx(
        'sg-window overflow-hidden border border-white/[0.09] bg-[#0b0b0e]',
        !isSquare && 'rounded-[12px]',
        className,
      )}
    >
      <div className="sg-window-bar flex h-10 items-center gap-3 border-b border-white/[0.07] px-4">
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="h-2 w-2 rounded-full bg-white/15" />
          <span className="h-2 w-2 rounded-full bg-white/15" />
          <span className="h-2 w-2 rounded-full bg-white/15" />
        </div>
        {kind === 'browser' ? (
          <span className="mx-auto flex min-w-0 max-w-[70%] items-center gap-2 rounded-md bg-white/[0.05] px-3 py-1 font-mono text-[0.72rem] text-white/40">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-galaxy-400" aria-hidden="true" />
            <span className="truncate">{title}</span>
          </span>
        ) : (
          <span className="min-w-0 truncate font-mono text-[0.75rem] text-white/40">{title}</span>
        )}
        <div className={clsx('flex items-center gap-1', kind === 'browser' ? 'w-10 justify-end' : 'ml-auto')}>
          {actions}
        </div>
      </div>
      {children}
    </div>
  );
}

/** Status chip used by every fill result on the page. */
export function StatusChip({ status }: { status: string }): JSX.Element {
  const tone =
    status === 'ok' || status === 'match' || status === 'written'
      ? 'border-galaxy-400/40 bg-galaxy-500/15 text-galaxy-100'
      : status === 'escalate' || status === 'needs'
        ? 'border-nebula-400/40 bg-nebula-400/10 text-nebula-300'
        : 'border-white/15 bg-white/[0.04] text-white/60';
  return <span className={clsx('inline-flex border px-1.5 py-px font-mono text-[0.72rem]', tone)}>{status}</span>;
}
