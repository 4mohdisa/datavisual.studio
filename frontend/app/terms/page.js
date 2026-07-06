import LegalPage, { Section } from '../../components/legal/LegalPage';

export const metadata = { title: 'Terms of use — datavisual.studio' };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of use" updated="6 July 2026">
      <Section title="The service">
        <p>
          datavisual.studio is provided free of charge. You bring your own AI provider keys
          (OpenRouter required, Google Gemini optional) and pay those providers directly for
          any usage your account generates. We never bill you and never spend keys other
          than the ones you saved on your own account.
        </p>
      </Section>

      <Section title="Your responsibilities">
        <ul className="list-disc pl-5 flex flex-col gap-1.5 m-0">
          <li>Only upload or connect data you have the right to use.</li>
          <li>Keep your account and AI keys secure; usage billed by AI providers under your keys is your responsibility.</li>
          <li>Database connections must use read-only credentials wherever possible — imports are SELECT-only by design, but the credentials you enter are your own risk.</li>
          <li>Don&apos;t use the service to generate or distribute unlawful content, or attempt to access other users&apos; data.</li>
        </ul>
      </Section>

      <Section title="AI output">
        <p>
          Research reports, dashboards and predictions are produced by AI models and
          statistical methods. They can be wrong, incomplete or out of date. They are not
          financial, legal, medical or betting advice — verify anything you act on.
        </p>
      </Section>

      <Section title="Availability and data">
        <p>
          The service is provided &quot;as is&quot;, without warranty of any kind. It may be
          unavailable, rate-limited or discontinued at any time. Your data is stored on the
          platform&apos;s server and backed up on a best-effort basis — keep your own copies of
          source datasets and export anything you can&apos;t afford to lose.
        </p>
      </Section>

      <Section title="Liability">
        <p>
          To the maximum extent permitted by law, the maintainer is not liable for any
          damages arising from your use of the service, including AI provider costs, data
          loss or decisions made based on generated content.
        </p>
      </Section>

      <Section title="Changes">
        <p>
          These terms may change; the date above is updated when they do. Continued use of
          the service means you accept the current terms.
        </p>
      </Section>
    </LegalPage>
  );
}
