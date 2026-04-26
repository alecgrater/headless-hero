interface SkeletonProps {
  className?: string;
  rounded?: string;
}

export function Skeleton({ className = "h-4 w-full", rounded = "rounded-lg" }: SkeletonProps) {
  return <div className={`shimmer-skeleton ${rounded} ${className}`} />;
}

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={`h-4 ${i === lines - 1 ? "w-3/4" : "w-full"}`} />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 space-y-3 ${className}`}>
      <Skeleton className="h-5 w-1/2" />
      <SkeletonText lines={2} />
    </div>
  );
}

export function SkeletonImage({ className = "" }: { className?: string }) {
  return <Skeleton className={`aspect-video w-full ${className}`} rounded="rounded-xl" />;
}
