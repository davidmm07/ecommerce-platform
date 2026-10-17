import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ResponsiveImageData } from './ResponsiveImage';
import { ResponsiveImage } from './ResponsiveImage';

const image: ResponsiveImageData = {
  url: '/media/products/p/abc-640.webp',
  width: 1280,
  height: 960,
  placeholder: 'data:image/webp;base64,AAAA',
  sources: [
    { type: 'image/avif', srcset: '/media/products/p/abc-320.avif 320w' },
    { type: 'image/webp', srcset: '/media/products/p/abc-320.webp 320w' },
  ],
};

describe('ResponsiveImage', () => {
  it('renders modern formats, intrinsic size and lazy loading', () => {
    const { container } = render(
      <ResponsiveImage image={image} alt="Running Shoes" sizes="300px" />,
    );
    const img = screen.getByRole('img', { name: 'Running Shoes' });
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img).toHaveAttribute('decoding', 'async');
    expect(img).toHaveAttribute('width', '1280');
    expect(img).toHaveAttribute('height', '960');
    expect(img).toHaveAttribute('sizes', '300px');
    const sources = container.querySelectorAll('source');
    expect([...sources].map((source) => source.getAttribute('type'))).toEqual([
      'image/avif',
      'image/webp',
    ]);
    expect(sources[0]).toHaveAttribute('sizes', '300px');
    expect(container.querySelector('img[aria-hidden]')).toHaveAttribute('src', image.placeholder);
  });

  it('prioritizes above the fold images', () => {
    render(<ResponsiveImage image={image} alt="Hero" sizes="100vw" priority />);
    const img = screen.getByRole('img', { name: 'Hero' });
    expect(img).toHaveAttribute('loading', 'eager');
    expect(img).toHaveAttribute('fetchpriority', 'high');
  });

  it('fades in once loaded and falls back when the file is missing', () => {
    const { rerender } = render(<ResponsiveImage image={image} alt="Mug" sizes="64px" />);
    const img = screen.getByRole('img', { name: 'Mug' });
    expect(img.className).toContain('opacity-0');
    fireEvent.load(img);
    expect(img.className).toContain('opacity-100');

    fireEvent.error(img);
    expect(screen.getByRole('img', { name: 'Mug, no photo yet' })).toBeInTheDocument();

    rerender(<ResponsiveImage image={null} alt="Lamp" sizes="64px" />);
    expect(screen.getByRole('img', { name: 'Lamp, no photo yet' })).toBeInTheDocument();
  });
});
