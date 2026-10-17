import type { ErrorComponentProps } from '@tanstack/react-router';
import { Link, useRouter } from '@tanstack/react-router';
import { Compass } from 'lucide-react';

import { ApiError, describeError } from '@/shared/api/http';
import { Button } from '@/shared/ui/Button';
import { buttonClasses } from '@/shared/ui/styles';
import { EmptyState, ErrorState, Spinner } from '@/shared/ui/display';

export function NotFoundPage() {
  return (
    <EmptyState
      icon={<Compass className="size-10" aria-hidden />}
      title="Page not found"
      description="The page you are looking for does not exist or was moved."
      action={
        <Link to="/products" className={buttonClasses('primary')}>
          Back to the shop
        </Link>
      }
    />
  );
}

export function RouteError({ error, reset }: ErrorComponentProps) {
  const router = useRouter();
  if (error instanceof ApiError && error.status === 404) {
    return <NotFoundPage />;
  }
  return (
    <ErrorState
      message={describeError(error)}
      action={
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            reset();
            void router.invalidate();
          }}
        >
          Try again
        </Button>
      }
    />
  );
}

export function RoutePending() {
  return <Spinner />;
}
