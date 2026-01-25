"use client";

import { BookCard } from "@/components/domain/BookCard";

import { BookRow } from "@/components/domain/BookRow";

import { cn } from "@/lib/utils";

import { usePlayerCurrentBook, usePlayerIsPlaying } from "@/store/playerStore";

import type { Book } from "@/types";



export interface LibraryBooksProps {

  books: Book[];

  viewMode: "grid" | "list";

  isSelectionMode: boolean;

  selectedBooks: string[];

  onToggleSelection: (asin: string) => void;

  onPlay: (asin: string) => void;

  onDownload: (asin: string) => void;

  onConvert: (params: { asin: string }) => void;

  onDelete: (asin: string) => void;

  className?: string;

}



export function LibraryBooks({

  books,

  viewMode,

  isSelectionMode,

  selectedBooks,

  onToggleSelection,

  onPlay,

  onDownload,

  onConvert,

  onDelete,

  className,

}: LibraryBooksProps) {

  const { id: currentBookId } = usePlayerCurrentBook();

  const isPlaying = usePlayerIsPlaying();



  return (

    <div className={cn(

      "pb-10",

      viewMode === "grid" 

        ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6"

        : "space-y-1",

      className

    )}>

      {books.map((book) => {

        const isCurrent = book.asin === currentBookId;

        

                return viewMode === "grid" ? (

        

                  <BookCard

        

                    key={book.asin}

        

                    book={book}

        

                    selectable={isSelectionMode}

        

                    selected={selectedBooks.includes(book.asin)}

        

                    isCurrent={isCurrent}

        

                    isPlaying={isPlaying}

        

                    onSelect={() => onToggleSelection(book.asin)}

        

                    onPlay={() => onPlay(book.asin)}

        

                    onDownload={() => onDownload(book.asin)}

        

                    onConvert={() => onConvert({ asin: book.asin })}

        

                    onAction={(action) => {

        

                      if (action === "delete") onDelete(book.asin);

        

                    }}

        

                  />

        

                ) : (

        

                  <BookRow

        

                    key={book.asin}

        

                    book={book}

        

                    selectable={isSelectionMode}

        

                    selected={selectedBooks.includes(book.asin)}

        

                    isCurrent={isCurrent}

        

                    isPlaying={isPlaying}

        

                    onSelect={() => onToggleSelection(book.asin)}

        

                    onPlay={() => onPlay(book.asin)}

        

                    onDownload={() => onDownload(book.asin)}

        

                    onConvert={() => onConvert({ asin: book.asin })}

        

                    onDelete={() => onDelete(book.asin)}

        

                    onRowClick={(b) => {

        

                      if (isSelectionMode) {

        

                        onToggleSelection(b.asin);

        

                      } else {

        

                        onPlay(b.asin);

        

                      }

        

                    }}

        

                  />

        

                );

        

        

      })}

    </div>

  );

}
