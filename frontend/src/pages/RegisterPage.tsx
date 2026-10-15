import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { ShoppingBasket } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
import { useAuthStore } from '@/lib/auth-store';
import { fetchOne, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import type { AppConfig } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Skeleton } from '@/ui/skeleton';

const schema = z.object({
  username: z.string().min(3, 'Use at least 3 characters.'),
  password: z.string().min(8, 'Use at least 8 characters.'),
});

type Values = z.infer<typeof schema>;

export default function RegisterPage() {
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
    try {
      await axios.post(`${import.meta.env.VITE_API_URL ?? '/api'}/register/`, values);
      const ok = await login(values.username, values.password);
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
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-muted/40 p-4">
      <div className="flex items-center gap-2.5">
        <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ShoppingBasket className="size-4.5" aria-hidden />
        </span>
        <span className="text-lg font-semibold tracking-tight">Basket Campaigns</span>
      </div>
      {config.isLoading ? (
        <div className="w-full max-w-sm space-y-4 rounded-xl border border-border bg-card p-6 shadow-sm">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : config.data && !config.data.registration_enabled ? (
        <div className="w-full max-w-sm space-y-3 rounded-xl border border-border bg-card p-6 text-center shadow-sm">
          <h1 className="text-xl font-semibold tracking-tight">Registration is disabled</h1>
          <p className="text-sm text-muted-foreground">
            This instance is set up for a single admin. Ask the owner to create your account, or sign in instead.
          </p>
          <Link to="/login" className="text-sm font-medium text-primary hover:underline">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form
          onSubmit={onSubmit}
          noValidate
          className="w-full max-w-sm space-y-4 rounded-xl border border-border bg-card p-6 shadow-sm"
        >
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Create account</h1>
            <p className="mt-1 text-sm text-muted-foreground">A few seconds and you're in.</p>
          </div>
          {errors.root && <Alert variant="destructive">{errors.root.message}</Alert>}
          <Field label="Username" htmlFor="username" error={errors.username?.message}>
            <Input id="username" autoComplete="username" autoFocus {...register('username')} />
          </Field>
          <Field label="Password" htmlFor="password" error={errors.password?.message} hint="At least 8 characters.">
            <Input id="password" type="password" autoComplete="new-password" {...register('password')} />
          </Field>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Have an account?{' '}
            <Link to="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </div>
  );
}
