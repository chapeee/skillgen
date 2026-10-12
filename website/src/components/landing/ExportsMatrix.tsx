import React, { useState } from 'react';
import clsx from 'clsx';
import { Button, CommandLine, CopyButton, Frame, Reveal } from './ui';
import { ArrowRightIcon, GitHubIcon } from './icons';
import { REPOSITORY_URL } from './constants';

const DESTINATIONS = [
  { id: 'upload', name: 'Skill upload', where: 'Claude or ChatGPT skill settings' },
  { id: 'local', name: 'Local skills', where: 'Claude Code or Cowork, your machine' },
  { id: 'plugin', name: 'Claude Code plugin', where: 'Install or publish' },
  { id: 'chatgpt', name: 'ChatGPT & Codex plugin', where: 'OpenAI plugin portal' },
];

type Row = { label: string; values: React.ReactNode[]; isCommand?: boolean };

const CHECK = <span className="text-galaxy-200">✓</span>;

const ROWS: Row[] = [
  {
    label: 'Command',
    isCommand: true,
    values: ['skillgendev export --one-skill --zip', 'skillgendev export', 'skillgendev export --plugin --zip', 'skillgendev export-chatgpt --zip'],
  },
  {
    label: 'You get',
    values: [
      'dist/skill/<name>.zip',
      'skills/<page>/ to copy into ~/.claude/skills/',
      '.claude-plugin/plugin.json + skills/<page>/',
      'plugin.json + skills/<name>/ + assets/icon.svg',
    ],
  },
  { label: 'SKILL.md files', values: ['exactly one', 'one per page', 'one per page', 'exactly one'] },
  { label: 'Pages inside', values: ['a file per page', 'a folder per page', 'a folder per page', 'a file per page'] },
  { label: 'Spec checks + secret scan', values: [CHECK, CHECK, CHECK, CHECK] },
  { label: 'MANIFEST.sha256', values: [CHECK, CHECK, CHECK, CHECK] },
  { label: 'All four fill methods', values: [CHECK, CHECK, CHECK, CHECK] },
];

function CellValue({ row, index }: { row: Row; index: number }): JSX.Element {
  const value = row.values[index];
  if (row.isCommand && typeof value === 'string') {
    return (
      <span className="flex items-center justify-between gap-1 font-mono text-[0.78rem] text-white/70">
        <span className="min-w-0 break-words">{value}</span>
        <CopyButton text={value} className="h-7 w-7" />
      </span>
    );
  }
  return <span className="font-mono text-[0.78rem] leading-relaxed text-white/50 [overflow-wrap:anywhere]">{value}</span>;
}

export default function ExportsMatrix(): JSX.Element {
  const [active, setActive] = useState(0);

  return (
    <section id="exports" className="sg-section sg-tone-teal relative py-28 sm:py-36" aria-labelledby="exports-title">
      <div className="sg-shell">
        {/* The intro is hidden by request; the heading stays for screen readers. */}
        <h2 id="exports-title" className="sr-only">
          Exports: one compile, every AI that takes skills
        </h2>

        {/* Small screens: pick a destination, see its column. */}
        <Reveal className="md:hidden">
          <div className="flex gap-1 overflow-x-auto pb-2" role="tablist" aria-label="Export destinations">
            {DESTINATIONS.map((destination, index) => (
              <button
                key={destination.id}
                type="button"
                role="tab"
                aria-selected={index === active}
                onClick={() => setActive(index)}
                className={clsx(
                  'shrink-0 border px-3 py-2 text-[0.85rem]',
                  index === active ? 'border-galaxy-400/50 bg-galaxy-500/10 text-white/90' : 'border-white/[0.08] text-white/40',
                )}
              >
                {destination.name}
              </button>
            ))}
          </div>
          <dl className="sg-window mt-3 border border-white/[0.08] bg-[#0b0b0e]">
            <div className="border-b border-white/[0.06] p-4">
               <dt className="text-[1rem] font-medium text-white/90">{DESTINATIONS[active].name}</dt>
               <dd className="mt-1 text-[0.875rem] text-white/40">{DESTINATIONS[active].where}</dd>
            </div>
            {ROWS.map((row) => (
              <div key={row.label} className="grid grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)] gap-3 border-b border-white/[0.06] px-4 py-3 last:border-b-0">
                <dt className="text-[0.82rem] text-white/40">{row.label}</dt>
                <dd className="min-w-0">
                  <CellValue row={row} index={active} />
                </dd>
              </div>
            ))}
          </dl>
        </Reveal>

        {/* Wider screens: the whole matrix, one column in focus. */}
        <Reveal className="hidden md:block">
          <div className="sg-card grid grid-cols-[minmax(10rem,0.8fr)_repeat(4,minmax(0,1fr))] border border-white/[0.08] px-6 pb-2" role="table" aria-label="Export destinations compared">
            <div role="row" className="contents">
              <div role="columnheader" className="border-b border-white/[0.08] pb-5" />
              {DESTINATIONS.map((destination, index) => (
                <button
                  key={destination.id}
                  type="button"
                  role="columnheader"
                  onMouseEnter={() => setActive(index)}
                  onFocus={() => setActive(index)}
                  onClick={() => setActive(index)}
                  className={clsx(
                    'relative border-b px-4 pb-5 pt-5 text-left transition-colors duration-300',
                    index === active ? 'border-galaxy-400/60 bg-galaxy-500/[0.07]' : 'border-white/[0.08]',
                  )}
                >
                  {index === active && (
                    <>
                      <span className="absolute left-0 top-0 h-3 w-3 border-l border-t border-galaxy-300" aria-hidden="true" />
                      <span className="absolute right-0 top-0 h-3 w-3 border-r border-t border-galaxy-300" aria-hidden="true" />
                    </>
                  )}
                  <span className={clsx('block text-[1rem] font-medium', index === active ? 'text-white/90' : 'text-white/60')}>
                    {destination.name}
                  </span>
                  <span className="mt-1 block text-[0.8rem] text-white/30">{destination.where}</span>
                </button>
              ))}
            </div>
            {ROWS.map((row) => (
              <div key={row.label} role="row" className="contents">
                <div role="rowheader" className="flex items-center border-b border-white/[0.06] py-4 pr-4 text-[0.875rem] text-white/50">
                  {row.label}
                </div>
                {DESTINATIONS.map((destination, index) => (
                  <div
                    key={destination.id}
                    role="cell"
                    className={clsx(
                      'flex items-center border-b border-white/[0.06] px-4 py-4 transition-colors duration-300',
                      index === active && 'bg-galaxy-500/[0.07]',
                    )}
                  >
                    <CellValue row={row} index={index} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal className="mt-6 flex justify-end">
          <Button to="/docs/guides/exporting/" variant="ghost" className="h-10">
            Which export goes where
            <ArrowRightIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Button>
        </Reveal>

        <Reveal className="mt-16">
          <Frame tone="accent">
            <div className="sg-card flex flex-col gap-6 border border-white/[0.08] p-6 sm:p-8 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-[1.1rem] font-medium tracking-[-0.01em] text-white/90">Try it on your own app</p>
                <p className="mt-1 text-[0.875rem] text-white/40">Pre-alpha, on PyPI. Python 3.10+.</p>
                <div className="mt-5 max-w-2xl space-y-2">
                  <CommandLine command='uv tool install "skillgendev[probe]"' />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button to="/docs/getting-started/quick-start/">
                  Quick start
                  <ArrowRightIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </Button>
                <Button href={REPOSITORY_URL} variant="secondary">
                  <GitHubIcon className="h-4 w-4" /> GitHub
                </Button>
              </div>
            </div>
          </Frame>
        </Reveal>
      </div>
    </section>
  );
}
