import { SignIn } from '@clerk/nextjs';
import AuthShell, { OpenModeNote } from '../../../components/AuthShell';

export const metadata = { title: 'Sign in', robots: { index: false } };

const authEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function SignInPage() {
  return (
    <AuthShell mode="sign-in">
      {authEnabled
        ? <SignIn fallbackRedirectUrl="/studio" signUpFallbackRedirectUrl="/studio" />
        : <OpenModeNote />}
    </AuthShell>
  );
}
