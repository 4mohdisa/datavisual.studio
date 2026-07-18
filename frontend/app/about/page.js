import Link from 'next/link';
import LegalPage, { Section } from '../../components/legal/LegalPage';

export const metadata = {
  title: 'About',
  description:
    'Who built datavisual.studio, what it does, and the engineering decisions behind it — an LLM that emits query specs while deterministic Python does the arithmetic.',
  alternates: { canonical: '/about' },
};

const SITE = process.env.NEXT_PUBLIC_SITE_URL || 'https://datavisual.studio';

// Person + BreadcrumbList structured data (SEO, Phase 6e).
const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Person',
      name: 'Mohammed Isa',
      alternateName: '@4mohdisa',
      url: 'https://isaxcode.com',
      sameAs: ['https://github.com/4mohdisa'],
      jobTitle: 'Software engineer',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: SITE },
        { '@type': 'ListItem', position: 2, name: 'About', item: `${SITE}/about` },
      ],
    },
  ],
};

export default function AboutPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <LegalPage title="About datavisual.studio" updated="18 July 2026">
        <Section title="What it is">
          <p>
            datavisual.studio turns a dataset into a living, editable dashboard. Upload a file or
            connect a SQL database or REST API, and you get charts and metrics you can refine by
            chatting in plain language. From the same place, a council of AI models can research a
            question against the live web and pin its findings — cited — onto the dashboard. One
            &ldquo;Update&rdquo; later re-pulls the data and re-runs that research, and tells you
            exactly what changed.
          </p>
          <p>It is free. You bring your own AI keys, and your data stays on the platform&apos;s own server.</p>
        </Section>

        <Section title="Who built it">
          <p>
            I&apos;m{' '}
            <a href="https://isaxcode.com" target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] underline underline-offset-2">
              Mohammed Isa
            </a>{' '}
            (
            <a href="https://github.com/4mohdisa" target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] underline underline-offset-2">
              @4mohdisa
            </a>
            ), a software engineer. datavisual.studio is a solo project — product, backend, frontend,
            infrastructure and design. The source is open under the MIT license.
          </p>
        </Section>

        <Section title="What you can do with it">
          <ul className="list-disc pl-5 flex flex-col gap-1.5 m-0">
            <li>Build a dashboard instantly from CSV, Excel, JSON, or a live SQL/REST connection.</li>
            <li>Edit it by chat (&ldquo;add a bar chart of revenue by region&rdquo;) or by hand.</li>
            <li>Ask questions of your data and get grounded, defensible numbers back.</li>
            <li>Run a multi-model research council that reads the live web and writes a cited report.</li>
            <li>Monitor it: one update surfaces value deltas and fresh sources since last time.</li>
            <li>Share a read-only public link, or export to PDF / HTML.</li>
          </ul>
        </Section>

        <Section title="How it&apos;s built — and why">
          <p>
            The stack is a <strong>Next.js</strong> frontend on Vercel talking through a single
            authenticated proxy to a <strong>FastAPI</strong> backend on AWS, with <strong>Clerk</strong>{' '}
            for identity. There is deliberately <strong>no database</strong>: all state is JSON on
            disk. For a single-tenant, single-replica product that removes an entire operational
            surface and makes the security model tractable — one directory is the trust boundary.
          </p>
          <p>
            The decision I care about most: <strong>the language model never does arithmetic.</strong>{' '}
            It translates a question into a JSON <em>query spec</em>; a deterministic Python engine
            executes that spec and phrases the answer from the result. A measure that&apos;s a level
            (MRR, headcount) is never summed across time; a &ldquo;how many&rdquo; that the model
            accidentally split by a category it wasn&apos;t asked about is collapsed back to the total.
            Every number the product shows can be defended — because a person, or a test, can re-derive
            it. Charts carry a deterministic text alternative for screen readers for the same reason:
            the summary is generated from the plotted numbers, not narrated by an LLM.
          </p>
          <p>
            A fuller write-up of the architecture and its invariants lives in the repository. If you
            want to see how it fits together, that&apos;s the place to start.
          </p>
          <p>
            <Link href="/studio" className="text-[var(--accent)] underline underline-offset-2">Open the studio →</Link>
          </p>
        </Section>
      </LegalPage>
    </>
  );
}
