import { Container } from "./Container";

export function LoadingState({ message = "Loading news coverage..." }: { message?: string }) {
  return (
    <Container className="py-16">
      <div className="flex flex-col items-center justify-center space-y-4">
        <div className="w-10 h-10 border-2 border-secondary border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-medium text-muted">{message}</p>
      </div>

      {/* BroadSheet Wire Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="border border-border p-4 rounded space-y-3">
            <div className="h-4 bg-border rounded w-1/4" />
            <div className="h-6 bg-border rounded w-3/4" />
            <div className="h-40 bg-border rounded w-full" />
            <div className="space-y-2 pt-2">
              <div className="h-3 bg-border rounded w-full" />
              <div className="h-3 bg-border rounded w-5/6" />
            </div>
          </div>
        ))}
      </div>
    </Container>
  );
}
