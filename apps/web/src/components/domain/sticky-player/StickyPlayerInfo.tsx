import * as React from "react";
import { cn } from "@/lib/utils";

export interface StickyPlayerInfoProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  subtitle?: string;
  onClick?: () => void;
}

export function StickyPlayerInfo({
  title,
  subtitle,
  onClick,
  className,
  ...props
}: StickyPlayerInfoProps) {
  return (
    <div
      className={cn(
        "hidden sm:flex flex-col justify-center min-w-0 w-48 lg:w-64 cursor-pointer hover:text-primary transition-colors",
        className
      )}
      onClick={onClick}
      {...props}
    >
      <h4 className="truncate text-sm font-semibold leading-tight" title={title}>
        {title}
      </h4>
      {subtitle && (
        <p className="truncate text-xs text-muted-foreground mt-0.5" title={subtitle}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
