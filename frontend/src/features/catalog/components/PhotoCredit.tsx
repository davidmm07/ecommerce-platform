import type { ImageCredit } from '../types';

function safeHref(url: string | null): string | undefined {
  return url && /^https?:\/\//i.test(url) ? url : undefined;
}

export function PhotoCredit({ credit }: { credit: ImageCredit | null }) {
  if (!credit) {
    return null;
  }
  const source = safeHref(credit.source_url);
  const license = safeHref(credit.license_url);
  const linkClasses = 'underline decoration-line-strong underline-offset-2 hover:text-fg';
  return (
    <p className="text-xs text-fg-muted">
      Photo:{' '}
      {source ? (
        <a href={source} target="_blank" rel="noopener noreferrer nofollow" className={linkClasses}>
          {credit.author}
        </a>
      ) : (
        credit.author
      )}
      ,{' '}
      {license ? (
        <a
          href={license}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className={linkClasses}
        >
          {credit.license}
        </a>
      ) : (
        credit.license
      )}
    </p>
  );
}
