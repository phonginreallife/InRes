'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function ProjectSchedulesPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    if (params.id) {
      router.replace(`/schedules?project_id=${params.id}`);
    }
  }, [params.id, router]);

  return (
    <div className="p-6 flex items-center justify-center">
      <div className="animate-pulse text-text-secondary">
        Redirecting to schedules...
      </div>
    </div>
  );
}
