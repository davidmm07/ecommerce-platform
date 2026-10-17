import { useQuery, useSuspenseQuery } from '@tanstack/react-query';
import { getRouteApi, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/shared/api/http';
import { PageHeader, Spinner } from '@/shared/ui/display';

import { ProductForm } from '../components/ProductForm';
import { ProductImageManager } from '../components/ProductImageManager';
import { changedFields, toProductInput } from '../product-form';
import { categoriesQuery, productQuery, useCreateProduct, useUpdateProduct } from '../queries';

export function NewProductPage() {
  const navigate = useNavigate();
  const categories = useQuery(categoriesQuery());
  const createProduct = useCreateProduct();

  return (
    <>
      <PageHeader title="New product" description="Add a product to the catalog." />
      {categories.data ? (
        <ProductForm
          categories={categories.data}
          submitLabel="Create product"
          onCancel={() => void navigate({ to: '/admin/products' })}
          onSubmit={async (values) => {
            const product = await createProduct.mutateAsync(toProductInput(values));
            toast.success(`${product.name} was created, add a photo next`);
            await navigate({
              to: '/admin/products/$productId/edit',
              params: { productId: product.id },
            });
          }}
        />
      ) : (
        <Spinner />
      )}
    </>
  );
}

const editRoute = getRouteApi('/admin/products/$productId/edit');

export function EditProductPage() {
  const { productId } = editRoute.useParams();
  const navigate = useNavigate();
  const { data: product, refetch } = useSuspenseQuery(productQuery(productId));
  const categories = useQuery(categoriesQuery());
  const updateProduct = useUpdateProduct();
  const [formRevision, setFormRevision] = useState(0);

  return (
    <>
      <PageHeader
        title={`Edit ${product.name}`}
        description={`SKU ${product.sku}, version ${product.version}`}
      />
      {categories.data ? (
        <div className="grid items-start gap-6 lg:grid-cols-[1fr_24rem]">
          <ProductForm
            key={formRevision}
            product={product}
            categories={categories.data}
            submitLabel="Save changes"
            onCancel={() => void navigate({ to: '/admin/products' })}
            onSubmit={async (values) => {
              const changes = changedFields(product, values);
              if (Object.keys(changes).length === 0) {
                toast.info('Nothing changed');
                return;
              }
              try {
                await updateProduct.mutateAsync({ product, changes });
              } catch (error) {
                if (error instanceof ApiError && error.status === 412) {
                  await refetch();
                  setFormRevision((revision) => revision + 1);
                  toast.warning('Someone else changed this product. The latest version is loaded.');
                  return;
                }
                throw error;
              }
              toast.success('Changes saved');
              await navigate({ to: '/admin/products' });
            }}
          />
          <ProductImageManager product={product} />
        </div>
      ) : (
        <Spinner />
      )}
    </>
  );
}
