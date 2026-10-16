import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';
import { buttonVariants } from '@/ui/button';

export default function NotFoundPage() {
  return (
    <div className="enter flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <span className="flex size-14 items-center justify-center rounded-full bg-sage text-primary">
        <Compass className="size-7" aria-hidden />
      </span>
      <h1 className="mt-1 text-2xl font-semibold tracking-[-0.035em]">Page not found</h1>
      <p className="text-sm text-muted-foreground">The page you're looking for doesn't exist or moved.</p>
      <Link to="/" className={buttonVariants({ variant: 'outline' })}>
        Back to dashboard
      </Link>
    </div>
  );
}
