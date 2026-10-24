import { cn } from '@/lib/utils';

/**
 * Word-by-word headline reveal, mirroring the staged entrance on the reference
 * design.
 *
 * Implemented with a CSS keyframe plus a per-word `animation-delay` rather than
 * framer-motion: the effect is a one-shot entrance with no gesture handling or
 * layout projection, so an animation library would add bundle weight for
 * something two declarations do. `prefers-reduced-motion` disables it outright
 * (see `.showcase-word` in `globals.css`).
 *
 * Words are separated by a plain space so the headline can still wrap at narrow
 * widths; a non-breaking space would hold the whole line on one line and let it
 * overflow the panel.
 */
export function AnimatedHeading({
  text,
  className,
  wordClassName,
  delayStep = 90
}: {
  text: string;
  className?: string;
  wordClassName?: string;
  /** Milliseconds between successive words. */
  delayStep?: number;
}) {
  const words = text.split(' ');

  return (
    <span className={cn('inline-block', className)}>
      {words.map((word, index) => (
        <span
          key={`${word}-${index}`}
          className='showcase-word inline-block'
          style={{ animationDelay: `${index * delayStep}ms` }}
        >
          <span className={cn('inline-block', wordClassName)}>{word}</span>
          {index < words.length - 1 ? ' ' : null}
        </span>
      ))}
    </span>
  );
}
