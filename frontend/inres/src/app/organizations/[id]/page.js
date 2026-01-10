'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function OrganizationDetailPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    // Redirect to organization's projects page
    if (params.id) {
      router.replace(`/organizations/${params.id}/projects`);
    }
  }, [params.id, router]);

  return (
    <div className="p-6 flex items-center justify-center">
      <div className="animate-pulse text-text-secondary">
        Loading organization...
      </div>
    </div>
  );
}
