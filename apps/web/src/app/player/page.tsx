"use client";

import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { PlayerContainer } from "./components/PlayerContainer";

export default function PlayerPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-screen">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      }
    >
      <PlayerContainer />
    </Suspense>
  );
}