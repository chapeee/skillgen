import React from 'react';
import Head from '@docusaurus/Head';
import useBaseUrl from '@docusaurus/useBaseUrl';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Hero from '../components/landing/Hero';
import StickyNav from '../components/landing/StickyNav';
import ProofStrip from '../components/landing/ProofStrip';
import ProblemSection from '../components/landing/ProblemSection';
import StorySection from '../components/landing/StorySection';
import SkillExplorer from '../components/landing/SkillExplorer';
import FillDemo from '../components/landing/FillDemo';
import HandoffSection from '../components/landing/HandoffSection';
import FaqSection from '../components/landing/FaqSection';
import { FinalCallToAction, LandingFooter } from '../components/landing/ClosingSection';
import BinaryCursor from '../components/landing/binary/BinaryCursor';

const TITLE = 'skillgendev: compile your app’s code into Agent Skills';
const DESCRIPTION =
  'skillgendev reads a web app’s code route by route and writes one Agent Skill per page, so Claude, Cowork or any AI with a browser can fill its forms in one call.';

// The landing page renders outside the docs layout so its hero can own the
// full viewport, as in the design reference.
export default function Home(): JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  // Social cards and canonical links need absolute URLs.
  const pageUrl = `${siteConfig.url}${useBaseUrl('/')}`;
  const socialCard = `${siteConfig.url}${useBaseUrl('/img/social-card.png')}`;
  return (
    <div className="landing">
      <Head>
        <title>{TITLE}</title>
        <meta name="description" content={DESCRIPTION} />
        <meta property="og:title" content={TITLE} />
        <meta property="og:description" content={DESCRIPTION} />
        <link rel="canonical" href={pageUrl} />
        <meta property="og:url" content={pageUrl} />
        <meta property="og:image" content={socialCard} />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta property="og:image:alt" content="skillgendev: where app code and Agent Skills align" />
        <meta name="twitter:title" content={TITLE} />
        <meta name="twitter:description" content={DESCRIPTION} />
        <meta name="twitter:image" content={socialCard} />
      </Head>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:bg-white focus:px-4 focus:py-2 focus:text-black"
      >
        Skip to content
      </a>
      <BinaryCursor />
      <StickyNav />
      <Hero />
      <main id="main" className="sg-main relative">
        <ProofStrip />
        <ProblemSection />
        <StorySection />
        <SkillExplorer />
        <FillDemo />
        <HandoffSection />
        <FaqSection />
        <FinalCallToAction />
        <LandingFooter />
      </main>
    </div>
  );
}
