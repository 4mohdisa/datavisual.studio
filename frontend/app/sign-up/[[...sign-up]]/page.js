import { SignUp } from '@clerk/nextjs';
import AuthShell, { OpenModeNote } from '../../../components/AuthShell';

export const metadata = { title: 'Create your account', robots: { index: false } };

const authEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function SignUpPage() {
  return (
    <AuthShell mode="sign-up">
      {authEnabled
        ? <SignUp fallbackRedirectUrl="/studio" signInFallbackRedirectUrl="/studio" />
        : <OpenModeNote />}
    </AuthShell>
  );
}
