/** Joins class names, filtering out falsy values. */
export function cn(...classes: (string | undefined | false | null | 0)[]): string {
  return classes.filter(Boolean).join(' ');
}
