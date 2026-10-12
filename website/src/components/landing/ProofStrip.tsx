import React from 'react';
import { Reveal } from './ui';

// Every number here is countable in the repository.
const FACTS = [
  { value: '1', unit: 'skill', label: 'per page, each self-contained and shareable alone' },
  { value: '1', unit: 'call', label: 'to fill a whole page from SKILL.md' },
  { value: '4', unit: 'methods', label: 'to fill, chosen by what the AI’s browser can do' },
  { value: '0', unit: 'installs', label: 'where skills are used: no MCP, no extension' },
];

export default function ProofStrip(): JSX.Element {
  return (
    <section aria-label="skillgendev at a glance" className="sg-proof-strip relative border-y border-white/[0.06]">
      <div className="sg-shell">
        <ul className="grid grid-cols-2 lg:grid-cols-4">
          {FACTS.map((fact, index) => (
            <Reveal
              as="li"
              key={fact.label}
              delay={index * 70}
               className="relative border-white/[0.06] px-2 py-8 odd:border-r sm:px-6 lg:border-r lg:py-10 lg:last:border-r-0 [&:nth-child(-n+2)]:border-b lg:[&:nth-child(-n+2)]:border-b-0"
            >
              <div className="flex items-baseline gap-2">
                 <span className="text-[2.25rem] font-light leading-none tracking-[-0.04em] text-white/90 sm:text-[2.6rem]">
                  {fact.value}
                </span>
                 <span className="font-mono text-[0.72rem] uppercase tracking-[0.14em] text-galaxy-300">{fact.unit}</span>
              </div>
               <p className="mt-3 max-w-[15rem] text-[0.875rem] leading-snug text-white/40">{fact.label}</p>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
