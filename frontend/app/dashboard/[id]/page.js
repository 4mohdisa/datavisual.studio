import Dashboard from '../../../components/Dashboard';

export default async function DashboardPage({ params }) {
  const { id } = await params;
  return <Dashboard id={id} />;
}
