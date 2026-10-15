import { Navigate } from 'react-router-dom';
import AppShell from './AppShell';
import { useAuthStore } from '@/lib/auth-store';

export default function Protected() {
  const access = useAuthStore((s) => s.access);
  if (!access) return <Navigate to="/login" replace />;
  return <AppShell />;
}
