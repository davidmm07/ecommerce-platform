import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PhotoCredit } from './PhotoCredit';

describe('PhotoCredit', () => {
  it('links the author and license with safe attributes', () => {
    render(
      <PhotoCredit
        credit={{
          author: 'Jane Doe',
          license: 'CC BY 2.0',
          source_url: 'https://www.flickr.com/photos/example/1',
          license_url: 'https://creativecommons.org/licenses/by/2.0/',
        }}
      />,
    );
    const author = screen.getByRole('link', { name: 'Jane Doe' });
    expect(author).toHaveAttribute('href', 'https://www.flickr.com/photos/example/1');
    expect(author).toHaveAttribute('rel', 'noopener noreferrer nofollow');
    expect(screen.getByRole('link', { name: 'CC BY 2.0' })).toHaveAttribute(
      'href',
      'https://creativecommons.org/licenses/by/2.0/',
    );
  });

  it('renders plain text for missing or unsafe links', () => {
    render(
      <PhotoCredit
        credit={{
          author: 'Unknown',
          license: 'CC0',
          source_url: 'javascript:alert(1)',
          license_url: null,
        }}
      />,
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(/Unknown/)).toHaveTextContent('Photo: Unknown, CC0');
  });

  it('renders nothing without a credit', () => {
    const { container } = render(<PhotoCredit credit={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
