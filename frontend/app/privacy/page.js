import LegalPage, { Section } from '../../components/legal/LegalPage';

export const metadata = {
  title: 'Privacy policy',
  description: 'How datavisual.studio stores your data and handles your AI provider keys.',
  alternates: { canonical: '/privacy' },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy" updated="6 July 2026">
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

      <Section title="Cookies">
        <p>
          The app uses only the cookies required for authentication sessions. There is no
          advertising or cross-site tracking.
        </p>
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
