import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';
import { buttonVariants } from '@/ui/button';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <Compass className="size-10 text-muted-foreground/60" aria-hidden />
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">The page you're looking for doesn't exist or moved.</p>
      <Link to="/" className={buttonVariants({ variant: 'outline' })}>
        Back to dashboard
      </Link>
    </div>
  );
}
