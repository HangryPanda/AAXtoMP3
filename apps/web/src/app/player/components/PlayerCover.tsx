import Image from "next/image";
import { Loader2, Headphones } from "lucide-react";
import { Book, LocalItem } from "@/types";

interface PlayerCoverProps {
  book?: Book | null;
  localItem?: LocalItem | null;
  coverUrl: string | null;
  isLoadingDetails: boolean;
  isPlayerLoading: boolean;
}

export function PlayerCover({
  book,
  coverUrl,
  isLoadingDetails,
  isPlayerLoading,
}: PlayerCoverProps) {
  return (
    <div
      className="aspect-square relative bg-card border border-border rounded-xl shadow-lg overflow-hidden group"
      style={{ viewTransitionName: "player-cover" }}
    >
      {isLoadingDetails ? (
        <div className="flex items-center justify-center h-full">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : coverUrl ? (
        <Image
          src={coverUrl}
          alt={book?.title || "Cover"}
          fill
          className="object-cover"
          sizes="(max-width: 1024px) 100vw, 320px"
          priority
        />
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground bg-muted/20">
          <Headphones className="w-16 h-16 mb-2 opacity-20" />
          <p className="text-sm">No Cover</p>
        </div>
      )}

      {isPlayerLoading && (
        <div className="absolute inset-0 bg-background/40 backdrop-blur-sm flex items-center justify-center">
          <Loader2 className="w-10 h-10 animate-spin text-primary" />
        </div>
      )}
    </div>
  );
}
