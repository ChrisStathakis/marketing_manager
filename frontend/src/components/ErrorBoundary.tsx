import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/ui/button';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render errors so the app shows a recovery card instead of a white screen. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-dvh items-center justify-center p-6">
          <div className="w-full max-w-md rounded-card border border-border bg-card p-6 text-center shadow-soft">
            <AlertTriangle className="mx-auto mb-3 size-8 text-warning" aria-hidden />
            <h1 className="text-lg font-semibold">Something went wrong</h1>
            <p className="mt-1 mb-4 text-sm break-words text-muted-foreground">{this.state.error.message}</p>
            <Button onClick={() => window.location.reload()}>Reload the app</Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
