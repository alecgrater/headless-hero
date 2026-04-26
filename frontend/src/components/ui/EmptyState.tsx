import { ReactNode } from "react";
import { Button } from "./Button";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="py-16 text-center space-y-3">
      <div className="w-12 h-12 text-neutral-600 mx-auto">{icon}</div>
      <p className="text-base font-medium text-neutral-400">{title}</p>
      {description && (
        <p className="text-sm text-neutral-500 max-w-xs mx-auto">{description}</p>
      )}
      {action && (
        <div className="pt-2">
          <Button variant="primary" onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      )}
    </div>
  );
}
