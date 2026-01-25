/**
 * Utility functions for the application
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combines clsx and tailwind-merge for conditional class names with proper
 * Tailwind CSS class merging. Conflicting utility classes are resolved
 * in favor of the last one specified.
 *
 * @param inputs - Class names, conditionals, arrays, or objects
 * @returns Merged class string with Tailwind conflicts resolved
 *
 * @example
 * cn("px-2 py-1", "px-4") // "py-1 px-4"
 * cn("bg-red-500", isActive && "bg-blue-500")
 * cn({ "font-bold": isBold, "text-lg": isLarge })
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Safe localStorage wrapper for SSR compatibility.
 * Returns a no-op storage during server-side rendering.
 */
export const safeLocalStorage: Storage =
  typeof window !== "undefined"
    ? localStorage
    : {
        length: 0,
        clear: () => {},
        getItem: () => null,
        key: () => null,
        removeItem: () => {},
        setItem: () => {},
      };
