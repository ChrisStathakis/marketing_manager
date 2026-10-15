import { Navigate, Outlet } from 'react-router-dom';
import Layout from './Layout';
import { useAuthStore } from '../lib/auth-store';

export default function Protected() {
  const access = useAuthStore((s) => s.access);
  if (!access) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}
