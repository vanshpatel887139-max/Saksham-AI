import { useState } from 'react';

export type LogoVariant = 'full' | 'icon';

export interface LogoProps {
  /**
   * 'full' is the lockup including the tagline, for the login hero only.
   * 'icon' is the mark alone, for everywhere it sits beside a nav label or a
   * page title.
   *
   * Defaulted rather than required, because the vast majority of call sites
   * want the mark. `height` below is the one prop that is not defaulted.
   */
  variant?: LogoVariant;
  /**
   * Rendered height in pixels, required so no call site can drift. An earlier
   * version defaulted this, which is how the sidebar and header ended up at
   * different sizes with nobody editing that line to cause it.
   */
  height: number;
  className?: string;
  /**
   * Override the accessible name. Pass "" where adjacent visible text already
   * names the app, so a screen reader does not announce the brand twice.
   */
  alt?: string;
}

/**
 * Candidate paths per variant, most-preferred first.
 *
 * The .svg leads so a real vector export takes over the moment it lands, with
 * no edit here: a missing .svg falls through to the .png. The fallback is
 * load-driven rather than status-code-driven, because the SPA catch-all
 * answers a request for a missing asset with HTTP 200 and the whole
 * index.html, which the browser then fails to decode as an image.
 *
 * Today both variants resolve to the same badge. The supplied source is one
 * integrated circular seal -- there is no separable icon and no tagline to
 * lock up -- so logo-full.png and logo-icon.png were the same file. That
 * placeholder is what the .png slot is for; it stays until the vectors land,
 * and it is the reason the two variants exist at all rather than one prop.
 */
const SOURCES: Record<LogoVariant, readonly string[]> = {
  full: ['/branding/logo-full.svg', '/branding/logo.png'],
  icon: ['/branding/logo-icon.svg', '/branding/logo.png'],
};

export function Logo({
  variant = 'icon',
  height,
  className = '',
  alt = 'Saksham',
}: LogoProps) {
  // Keyed by path rather than held as an index. An index would need resetting
  // whenever the variant changed, and that reset lands in an effect, so one
  // render would briefly resolve the wrong candidate. A map of "this path
  // failed to load" has no such window.
  const [missing, setMissing] = useState<Record<string, boolean>>({});

  const src = SOURCES[variant].find(c => !missing[c]);

  // Every candidate is gone. Rendering nothing beats a broken image, which
  // browsers draw as a torn-picture glyph in the middle of the header.
  if (!src) return null;

  return (
    <img
      src={src}
      alt={alt}
      // Height, never width: this is what holds the aspect ratio, so the mark
      // cannot stretch. display:block drops the baseline gap browsers put
      // under an inline image -- the usual cause of a logo reading as a few
      // pixels too high against the text beside it. No margin or padding is
      // set here on purpose; vertical placement is the flex parent's job.
      style={{ height, width: 'auto', display: 'block' }}
      decoding="async"
      onError={() => setMissing(prev => ({ ...prev, [src]: true }))}
      className={['shrink-0 select-none', className].filter(Boolean).join(' ')}
    />
  );
}

export default Logo;
