"use client";

import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { LibraryContainer } from "./components/LibraryContainer";

export default function LibraryPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    }>
      <LibraryContainer />
    </Suspense>
  );
}