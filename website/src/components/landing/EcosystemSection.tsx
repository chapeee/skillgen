import React from 'react';
import { Button, CommandLine, Frame, Reveal, SectionIntro, Window } from './ui';
import { ArrowRightIcon } from './icons';
import { GITSMITH_NPM_URL } from './constants';

const BUILT_ON = [
  { name: 'Graphify', role: 'Code graph, page slices and change impact' },
  { name: 'Claude Code', role: 'Reads each page’s code, read-only' },
  { name: 'ast-grep', role: 'Router hint packs, written in YAML' },
  { name: 'Playwright', role: 'Optional x/y probe on a dev copy' },
  { name: 'Agent Skills', role: 'The open format every skill follows' },
];

export default function EcosystemSection(): JSX.Element {
  return (
    <section id="ecosystem" className="sg-section sg-band sg-band-lavender sg-tone-violet relative py-28 sm:py-36" aria-labelledby="ecosystem-title">
      <div className="sg-shell">
        <SectionIntro
          index="07"
          tag="Ecosystem"
          id="ecosystem-title"
          title={
            <>
              Built on open tools.
              <br className="hidden sm:block" /> Pairs with Gitsmith.
            </>
          }
        />

        <Reveal className="mt-14">
          <ul className="grid grid-cols-2 border-l border-t border-dashed border-white/[0.1] sm:grid-cols-3 lg:grid-cols-5">
            {BUILT_ON.map((tool) => (
              <li key={tool.name} className="sg-card relative border-b border-r border-white/[0.08] px-6 py-8">
                <span className="absolute -left-[3px] -top-[3px] h-[5px] w-[5px] bg-white/30" aria-hidden="true" />
                <p className="text-[1.1rem] font-medium tracking-[-0.01em] text-white/90">{tool.name}</p>
                <p className="mt-2 text-[0.875rem] leading-snug text-white/40">{tool.role}</p>
              </li>
            ))}
          </ul>
        </Reveal>

        <div className="mt-20 grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-center">
          <Reveal>
            <p className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-galaxy-300">From the same maintainer</p>
            <h3 className="mt-4 text-[1.6rem] font-medium leading-[1.15] tracking-[-0.03em] text-white/90 sm:text-[1.9rem]">
              Gitsmith keeps the history as clean as the skills.
            </h3>
            <p className="mt-5 max-w-lg text-[1rem] leading-[1.65] text-white/50">
              skillgendev’s contributors write Conventional Commits: <code className="font-mono text-white/70">feat:</code>,{' '}
              <code className="font-mono text-white/70">fix:</code>, <code className="font-mono text-white/70">docs:</code>, one change
              each. Gitsmith is a commit CLI that prompts you through your project’s format from one{' '}
              <code className="font-mono text-white/70">.commitconfig.json</code>, previews the message before it commits, and
              can suggest one from a plain description with optional AI.
            </p>
            <p className="mt-4 max-w-lg text-[0.95rem] leading-[1.65] text-white/40">
              Small, well-labelled commits also make <code className="font-mono text-white/60">skillgendev check --since</code> easier
              to read: you can see which change made a skill stale.
            </p>
            <div className="mt-8 flex flex-wrap gap-2">
              <Button to="/docs/contributing/gitsmith/" variant="secondary">
                Use it with skillgendev
                <ArrowRightIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Button>
              <Button href={GITSMITH_NPM_URL} variant="ghost">
                gitsmith on npm
              </Button>
            </div>
          </Reveal>

          <Reveal delay={120} className="space-y-3">
            <CommandLine command="npm install -g gitsmith" />
            <Frame>
              <Window title=".commitconfig.json" isSquare>
                <pre className="m-0 overflow-x-auto bg-transparent p-5 font-mono text-[0.78rem] leading-[1.7] text-white/50">
                  <span className="text-white/40">{'{'}</span>
                  {'\n'}
                  {[
                    ['types', '["feat", "fix", "docs", "test", "refactor", "chore"]'],
                    ['askScope', 'true'],
                    ['scopes', '["routes", "analyze", "generate", "probe", "export", "docs"]'],
                    ['askTicket', 'false'],
                    ['askBreaking', 'true'],
                    ['format', '"{type}({scope}): {message}"'],
                    ['headerMaxLength', '72'],
                  ].map(([key, value], index, all) => (
                    <React.Fragment key={key}>
                      {'  '}
                      <span className="text-galaxy-300">"{key}"</span>: <span className="text-[#a5d6ff]">{value}</span>
                      {index < all.length - 1 ? ',' : ''}
                      {'\n'}
                    </React.Fragment>
                  ))}
                  <span className="text-white/40">{'}'}</span>
                </pre>
                <div className="border-t border-white/[0.06] px-5 py-3 font-mono text-[0.78rem]">
                  <span className="text-white/30">→ </span>
                  <span className="text-white/80">feat(analyze): show the analysis the live page</span>
                </div>
              </Window>
            </Frame>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
