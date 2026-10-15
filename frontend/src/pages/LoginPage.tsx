import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { ShoppingBasket } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
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
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-muted/40 p-4">
      <div className="flex items-center gap-2.5">
        <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ShoppingBasket className="size-4.5" aria-hidden />
        </span>
        <span className="text-lg font-semibold tracking-tight">Basket Campaigns</span>
      </div>
      <form
        onSubmit={onSubmit}
        noValidate
        className="w-full max-w-sm space-y-4 rounded-xl border border-border bg-card p-6 shadow-sm"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-sm text-muted-foreground">Manage campaigns, results and next steps.</p>
        </div>
        {errors.root && <Alert variant="destructive">{errors.root.message}</Alert>}
        <Field label="Username" htmlFor="username" error={errors.username?.message}>
          <Input id="username" autoComplete="username" autoFocus {...register('username')} />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" {...register('password')} />
        </Field>
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </Button>
        {config.data?.registration_enabled && (
          <p className="text-center text-sm text-muted-foreground">
            No account?{' '}
            <Link to="/register" className="font-medium text-primary hover:underline">
              Create one
            </Link>
          </p>
        )}
      </form>
    </div>
  );
}
