import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
import { AuthLayout } from '@/components/AuthLayout';
import { useAuthStore } from '@/lib/auth-store';
import { fetchOne, qk } from '@/lib/data';
import type { AppConfig } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';

const schema = z.object({
  username: z.string().min(1, 'Username is required.'),
  password: z.string().min(1, 'Password is required.'),
});

type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const login = useAuthStore((s) => s.login);
  const nav = useNavigate();
  const config = useQuery({
    queryKey: qk.config,
    queryFn: () => fetchOne<AppConfig>('/config/'),
    staleTime: Infinity,
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    const ok = await login(values.username, values.password);
    if (ok) {
      toast.success(`Welcome back, ${values.username}`);
      nav('/');
    } else {
      setError('root', { message: 'Invalid username or password.' });
    }
  });

  return (
    <AuthLayout>
      <span className="eyebrow">Welcome to your workspace</span>
      <h1 className="mt-3 mb-2 text-[clamp(1.6rem,2.5vw,2rem)] leading-tight font-semibold tracking-[-0.035em]">
        Good to see you.
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">Log in to pick up where you left off.</p>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {errors.root && <Alert variant="destructive">{errors.root.message}</Alert>}
        <Field label="Username" htmlFor="username" error={errors.username?.message}>
          <Input id="username" autoComplete="username" autoFocus {...register('username')} />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" {...register('password')} />
        </Field>
        <Button type="submit" className="mt-2 w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
          {!isSubmitting && <ArrowRight className="opacity-70" aria-hidden />}
        </Button>
        {config.data?.registration_enabled && (
          <p className="pt-1 text-center text-sm text-muted-foreground">
            No account?{' '}
            <Link to="/register" className="font-semibold text-primary hover:underline">
              Create one
            </Link>
          </p>
        )}
      </form>
    </AuthLayout>
  );
}
