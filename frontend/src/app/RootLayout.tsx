import { Link, Outlet } from '@tanstack/react-router';
import { Boxes, ShoppingCart } from 'lucide-react';
import type { ReactNode } from 'react';
import { Toaster } from 'sonner';

import { useCartCount } from '@/features/cart/cart-store';

const navLinkClasses =
  'shrink-0 rounded-md px-2 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 sm:px-3';

function NavLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className={navLinkClasses}
      activeProps={{ className: `${navLinkClasses} bg-slate-100 text-slate-900` }}
    >
      {children}
    </Link>
  );
}

export function RootLayout() {
  const cartCount = useCartCount();
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-4 sm:gap-4 sm:px-6">
          <Link to="/products" className="flex items-center gap-2 font-semibold text-slate-900">
            <span className="grid size-8 place-items-center rounded-lg bg-indigo-600 text-white">
              <Boxes className="size-5" aria-hidden />
            </span>
            <span className="hidden sm:inline">Commerce Platform</span>
          </Link>
          <nav
            aria-label="Main"
            className="flex flex-1 items-center gap-0.5 overflow-x-auto sm:gap-1"
          >
            <NavLink to="/products">Shop</NavLink>
            <NavLink to="/orders">Orders</NavLink>
            <span className="mx-2 hidden h-5 w-px bg-slate-200 sm:block" aria-hidden />
            <NavLink to="/admin/products">Products</NavLink>
            <NavLink to="/admin/import">Import</NavLink>
          </nav>
          <Link
            to="/cart"
            className="relative inline-flex shrink-0 items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 sm:px-3"
            aria-label={`Cart with ${cartCount} items`}
          >
            <ShoppingCart className="size-5" aria-hidden />
            <span className="hidden sm:inline">Cart</span>
            {cartCount > 0 && (
              <span className="absolute -right-1 -top-1 grid min-w-5 place-items-center rounded-full bg-indigo-600 px-1 text-xs font-semibold text-white">
                {cartCount}
              </span>
            )}
          </Link>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-500 sm:px-6">
          Portfolio project. Payments are simulated and no real charges are made.
        </div>
      </footer>
      <Toaster richColors position="top-right" closeButton />
    </div>
  );
}
