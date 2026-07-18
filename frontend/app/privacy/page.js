import LegalPage, { Section } from '../../components/legal/LegalPage';
import AnalyticsOptOut from '../../components/AnalyticsOptOut';

export const metadata = {
  title: 'Privacy policy',
  description: 'How datavisual.studio stores your data, handles your AI provider keys, and what its first-party analytics collect — with a one-click opt-out.',
  alternates: { canonical: '/privacy' },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy" updated="19 July 2026">
      <Section title="What this service is">
        <p>
          datavisual.studio is a free data-visualisation and research tool. You upload or
          connect data, build dashboards, and run AI-assisted research using your own AI
          provider keys.
        </p>
      </Section>

      <Section title="What we store">
        <p>
          Everything you create lives on the platform&apos;s own server — there is no external
          database and your content is never sold or shared with third parties:
        </p>
        <ul className="list-disc pl-5 flex flex-col gap-1.5 m-0">
          <li>Your account record: name, email and an internal user id.</li>
          <li>Datasets you upload or import from a database/API connection.</li>
          <li>Dashboards, research reports and their chat/edit history.</li>
          <li>Your AI provider keys (OpenRouter, Gemini), stored with your account and shown back to you only in masked form.</li>
          <li>Basic usage events (e.g. &quot;research run&quot;, &quot;dashboard created&quot;) used for operating the service.</li>
        </ul>
      </Section>

      <Section title="Authentication">
        <p>
          Sign-in is handled by Clerk. Clerk processes your login credentials and session;
          we receive only your identity (id, email, name). See Clerk&apos;s own privacy policy
          for how they handle authentication data.
        </p>
      </Section>

      <Section title="Where your data goes when you use AI features">
        <p>
          AI features run on the keys you provide. When you run research or edit a dashboard
          by chat, the relevant question, data excerpts and context are sent to the AI
          providers you configured (OpenRouter and/or Google Gemini) to produce the result.
          If you connect a database, imports are read-only and the results are stored as
          files on our server.
        </p>
      </Section>

      <Section title="Your control">
        <p>
          You can delete your dashboards and research from the app at any time, and replace
          or remove your AI keys from the &quot;AI keys&quot; panel. To have your account and all
          associated data removed entirely, contact the maintainer via GitHub.
        </p>
      </Section>

      <Section title="Cookies &amp; product analytics">
        <p>
          Two kinds of first-party cookies, and nothing more — no advertising, and no
          cross-site or third-party trackers:
        </p>
        <ul className="list-disc pl-5 flex flex-col gap-1.5 m-0">
          <li><strong>Authentication</strong> — the session cookies Clerk needs to keep you signed in.</li>
          <li>
            <strong>Product analytics</strong> — a first-party <code className="text-[var(--text)]">dv_anon_id</code>{' '}
            cookie (a random visitor id, kept ~12 months) plus a per-session id, so we can understand
            how the product is used and improve it.
          </li>
        </ul>
        <p>
          Each analytics event records the <strong>event name</strong> (e.g. &quot;landing_view&quot;,
          &quot;dashboard_created&quot;), those ids, the <strong>page path</strong> (never the query
          string), the referrer, and any UTM campaign parameters from your first visit. Events post to
          our own server — not to any third party.
        </p>
        <p>
          <strong>What is never in an analytics event: your data.</strong> Dataset contents, cell
          values, questions, dashboard specifics and API keys are excluded by design — event metadata
          is the only thing sent. Analytics records are retained on our server and are not sold or
          shared.
        </p>
        <p className="text-[var(--text)]">You can turn product analytics off in this browser — we also honour Global Privacy Control:</p>
        <AnalyticsOptOut />
      </Section>

      <Section title="Changes">
        <p>
          If this policy changes, the date above is updated. Substantial changes will be
          noted on the landing page.
        </p>
      </Section>
    </LegalPage>
  );
}
