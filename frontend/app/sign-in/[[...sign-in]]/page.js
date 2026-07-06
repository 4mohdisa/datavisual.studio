import { SignIn } from '@clerk/nextjs';

export default function SignInPage() {
  return (
    <div className="h-screen flex items-center justify-center bg-[var(--background)]">
      <SignIn fallbackRedirectUrl="/studio" signUpFallbackRedirectUrl="/studio" />
    </div>
  );
}
