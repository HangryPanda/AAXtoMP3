import * as React from "react";
import { cn } from "@/lib/utils";

export interface StickyPlayerRootProps extends React.HTMLAttributes<HTMLDivElement> {
  isVisible?: boolean;
  isAnimating?: boolean;
}

export function StickyPlayerRoot({
  className,
  isVisible = true,
  isAnimating = false,
  children,
  ...props
}: StickyPlayerRootProps) {
  if (!isVisible) return null;

  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-50 flex h-[72px] md:h-20 items-center gap-4 px-4 py-2 border-t bg-background/80 backdrop-blur-md shadow-lg transition-all duration-300 ease-out",
        isAnimating && "animate-in slide-in-from-bottom-full",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
