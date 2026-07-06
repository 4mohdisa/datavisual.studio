import AppShell from '../../../components/AppShell';

export default async function ChatPage({ params }) {
  const { id } = await params;
  return <AppShell conversationId={id} />;
}
