import * as React from "react";
import Image from "next/image";
import { BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StickyPlayerCoverProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string | null;
  alt?: string;
  onClick?: () => void;
}

export function StickyPlayerCover({
  src,
  alt = "Book Cover",
  onClick,
  className,
  ...props
}: StickyPlayerCoverProps) {
  return (
    <div
      className={cn(
        "relative h-14 w-14 shrink-0 cursor-pointer overflow-hidden rounded shadow-sm hover:scale-105 transition-transform bg-muted",
        className
      )}
      onClick={onClick}
      {...props}
    >
      {src ? (
        <Image
          src={src}
          alt={alt}
          fill
          className="object-cover"
          sizes="56px"
        />
      ) : (
        <div className="flex h-full items-center justify-center">
          <BookOpen className="h-6 w-6 text-muted-foreground/50" />
        </div>
      )}
    </div>
  );
}
