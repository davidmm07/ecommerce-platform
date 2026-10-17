import { ImageOff } from 'lucide-react';
import { useCallback, useState } from 'react';

import { cn } from '@/shared/lib/cn';

export type ResponsiveImageData = {
  url: string;
  width: number;
  height: number;
  placeholder: string;
  sources: Array<{ type: string; srcset: string }>;
};

type ResponsiveImageProps = {
  image: ResponsiveImageData | null | undefined;
  alt: string;
  sizes: string;
  priority?: boolean;
  fit?: 'cover' | 'contain';
  className?: string;
};

export function ResponsiveImage({ image, className, ...props }: ResponsiveImageProps) {
  if (!image) {
    return <MissingImage alt={props.alt} className={className} />;
  }
  return <LoadedImage key={image.url} image={image} className={className} {...props} />;
}

function LoadedImage({
  image,
  alt,
  sizes,
  priority = false,
  fit = 'cover',
  className,
}: ResponsiveImageProps & { image: ResponsiveImageData }) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const imageRef = useCallback((node: HTMLImageElement | null) => {
    if (node?.complete && node.naturalWidth > 0) {
      setLoaded(true);
    }
  }, []);
  const fitClass = fit === 'cover' ? 'object-cover' : 'object-contain';

  if (failed) {
    return <MissingImage alt={alt} className={className} />;
  }

  return (
    <div className={cn('relative overflow-hidden bg-media', className)}>
      <img
        src={image.placeholder}
        alt=""
        aria-hidden
        className={cn(
          'absolute inset-0 size-full scale-110 blur-xl transition-opacity duration-500',
          fitClass,
          loaded && 'opacity-0',
        )}
      />
      <picture>
        {image.sources.map((source) => (
          <source key={source.type} type={source.type} srcSet={source.srcset} sizes={sizes} />
        ))}
        <img
          ref={imageRef}
          src={image.url}
          alt={alt}
          width={image.width}
          height={image.height}
          sizes={sizes}
          loading={priority ? 'eager' : 'lazy'}
          fetchPriority={priority ? 'high' : 'auto'}
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
          className={cn(
            'relative size-full transition-opacity duration-500',
            fitClass,
            loaded ? 'opacity-100' : 'opacity-0',
          )}
        />
      </picture>
    </div>
  );
}

function MissingImage({ alt, className }: { alt: string; className?: string | undefined }) {
  return (
    <div
      role="img"
      aria-label={`${alt}, no photo yet`}
      className={cn('flex items-center justify-center bg-media text-fg-subtle', className)}
    >
      <ImageOff className="size-1/4 max-h-10 max-w-10" aria-hidden />
    </div>
  );
}
