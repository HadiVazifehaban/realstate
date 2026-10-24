'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export function ErrorBoundary({ children, fallback }: ErrorBoundaryProps) {
  const [state, setState] = React.useState<ErrorBoundaryState>({
    hasError: false,
    error: null
  });

  React.useEffect(() => {
    if (state.hasError) {
      console.error('[ErrorBoundary] Sidebar error captured:', state.error?.message);
    }
  }, [state.hasError, state.error]);

  if (state.hasError) {
    if (fallback) return <>{fallback}</>;

    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>خطا در رندر منو</CardTitle>
          <CardDescription>
            بخش منویی قابل نمایش نیست. لطفاً صفحه را Refresh کنید.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => setState({ hasError: false, error: null })}>
            تلاش مجدد
          </Button>
          {state.error && (
            <pre className="mt-2 text-xs text-rose-400 break-words">
              {state.error.message}
            </pre>
          )}
        </CardContent>
      </Card>
    );
  }

  return children;
}

export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>
) {
  return function ErrorBoundaryWrapper(props: P) {
    return (
      <ErrorBoundary>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}
