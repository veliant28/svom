import { ResetPasswordPage } from "@/features/auth/pages/reset-password-page";

export default async function ResetPasswordRoutePage({
  params,
}: {
  params: Promise<{ uid: string; token: string }>;
}) {
  const { uid, token } = await params;
  return <ResetPasswordPage uid={uid} token={token} />;
}
