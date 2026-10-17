import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
import { AuthLayout } from '@/components/AuthLayout';
import { useAuthStore } from '@/lib/auth-store';
import { fetchOne, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import type { AppConfig } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Alert } from '@/ui/alert';
import { Button, buttonVariants } from '@/ui/button';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Skeleton } from '@/ui/skeleton';

const schema = z.object({
  username: z.string().min(3, 'Use at least 3 characters.'),
  password: z.string().min(1, 'Password is required.'),
});

type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const login = useAuthStore((s) => s.login);
  const nav = useNavigate();
  const qc = useQueryClient();
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

  const firstUser = config.data ? !config.data.users_exist : false;

  const onSubmit = handleSubmit(async (values) => {
    try {
      await axios.post(`${import.meta.env.VITE_API_URL ?? '/api'}/register/`, values);
      const ok = await login(values.username, values.password);
      // Registration state changed (the first account closes sign-ups).
      qc.invalidateQueries({ queryKey: qk.config });
      if (ok) {
        toast.success('Account created');
        nav('/');
      } else {
        nav('/login');
      }
    } catch (error) {
      setError('root', { message: getErrorMessage(error, 'Registration failed.') });
    }
  });

  return (
    <AuthLayout>
      {config.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-7 w-44" />
          <Skeleton className="h-4 w-56" />
          <Skeleton className="mt-6 h-9.5 w-full" />
          <Skeleton className="h-9.5 w-full" />
          <Skeleton className="h-9.5 w-full" />
        </div>
      ) : config.data && !config.data.registration_enabled ? (
        <div className="text-center">
          <h1 className="text-[clamp(1.6rem,2.5vw,2rem)] leading-tight font-semibold tracking-[-0.035em]">
            Registration is disabled
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            This instance is set up for a single admin. Ask the owner to create your account, or sign in instead.
          </p>
          <Link to="/login" className={cn(buttonVariants({ variant: 'secondary' }), 'mt-6')}>
            Back to sign in
          </Link>
        </div>
      ) : (
        <>
          <span className="eyebrow">{firstUser ? 'First-time setup' : 'Welcome to your workspace'}</span>
          <h1 className="mt-3 mb-2 text-[clamp(1.6rem,2.5vw,2rem)] leading-tight font-semibold tracking-[-0.035em]">
            {firstUser ? 'Set up your admin account.' : 'Create your account.'}
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            {firstUser
              ? 'This first account is the admin — it can manage everything. Registration closes after this.'
              : "A few seconds and you're in."}
          </p>
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {errors.root && <Alert variant="destructive">{errors.root.message}</Alert>}
            <Field label="Username" htmlFor="username" error={errors.username?.message}>
              <Input id="username" autoComplete="username" autoFocus {...register('username')} />
            </Field>
            <Field label="Password" htmlFor="password" error={errors.password?.message} hint="Any password you like.">
              <Input id="password" type="password" autoComplete="new-password" {...register('password')} />
            </Field>
            <Button type="submit" className="mt-2 w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </Button>
            <p className="pt-1 text-center text-sm text-muted-foreground">
              Have an account?{' '}
              <Link to="/login" className="font-semibold text-primary hover:underline">
                Sign in
              </Link>
            </p>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
