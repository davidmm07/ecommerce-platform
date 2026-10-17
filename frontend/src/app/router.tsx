import type { QueryClient } from '@tanstack/react-query';
import {
  Navigate,
  createRootRouteWithContext,
  createRoute,
  createRouter,
} from '@tanstack/react-router';
import { z } from 'zod';

import { CartPage } from '@/features/cart/pages/CartPage';
import { AdminProductsPage } from '@/features/catalog/pages/AdminProductsPage';
import { ProductDetailPage } from '@/features/catalog/pages/ProductDetailPage';
import { EditProductPage, NewProductPage } from '@/features/catalog/pages/ProductEditorPages';
import { ShopPage } from '@/features/catalog/pages/ShopPage';
import { categoriesQuery, productQuery } from '@/features/catalog/queries';
import { parseAdminProductsSearch, parseShopSearch } from '@/features/catalog/search-params';
import { CheckoutPage } from '@/features/checkout/pages/CheckoutPage';
import { ImportPage } from '@/features/imports/pages/ImportPage';
import { orderQuery } from '@/features/orders/api';
import { OrderDetailPage } from '@/features/orders/pages/OrderDetailPage';
import { OrdersPage } from '@/features/orders/pages/OrdersPage';

import { RootLayout } from './RootLayout';
import { NotFoundPage, RouteError, RoutePending } from './RouteStates';

export type RouterContext = {
  queryClient: QueryClient;
};

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  notFoundComponent: NotFoundPage,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => <Navigate to="/products" replace />,
});

const shopRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/products',
  validateSearch: parseShopSearch,
  loader: ({ context }) => context.queryClient.ensureQueryData(categoriesQuery()),
  component: ShopPage,
});

const productRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/products/$productId',
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(productQuery(params.productId)),
  component: ProductDetailPage,
});

const cartRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cart',
  component: CartPage,
});

const checkoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/checkout',
  component: CheckoutPage,
});

const ordersSearch = z.object({
  email: z.string().trim().max(254).optional().catch(undefined),
  page: z.coerce.number().int().min(1).optional().catch(undefined),
});

const ordersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/orders',
  validateSearch: (search: Record<string, unknown>) => ordersSearch.parse(search),
  component: OrdersPage,
});

const orderSearch = z.object({
  placed: z.boolean().optional().catch(undefined),
});

const orderRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/orders/$orderId',
  validateSearch: (search: Record<string, unknown>) => orderSearch.parse(search),
  loader: ({ context, params }) => context.queryClient.ensureQueryData(orderQuery(params.orderId)),
  component: OrderDetailPage,
});

const adminProductsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/products',
  validateSearch: parseAdminProductsSearch,
  component: AdminProductsPage,
});

const newProductRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/products/new',
  loader: ({ context }) => context.queryClient.ensureQueryData(categoriesQuery()),
  component: NewProductPage,
});

const editProductRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/products/$productId/edit',
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.ensureQueryData(productQuery(params.productId)),
      context.queryClient.ensureQueryData(categoriesQuery()),
    ]),
  component: EditProductPage,
});

const importRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/import',
  component: ImportPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  shopRoute,
  productRoute,
  cartRoute,
  checkoutRoute,
  ordersRoute,
  orderRoute,
  adminProductsRoute,
  newProductRoute,
  editProductRoute,
  importRoute,
]);

export function createAppRouter(queryClient: QueryClient) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    defaultPreloadStaleTime: 0,
    defaultErrorComponent: RouteError,
    defaultPendingComponent: RoutePending,
    scrollRestoration: true,
  });
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
