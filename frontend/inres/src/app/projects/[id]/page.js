'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '../../../lib/api';
import { useAuth } from '../../../contexts/AuthContext';
import { useOrg } from '../../../contexts/OrgContext';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { session } = useAuth();
  const { currentOrg } = useOrg();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProject = async () => {
      if (!session?.access_token || !params.id) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        apiClient.setToken(session.access_token);
        const data = await apiClient.getProject(params.id);
        setProject(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching project:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchProject();
  }, [params.id, session]);

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-surface rounded w-1/4 mb-4"></div>
          <div className="h-4 bg-surface rounded w-1/2 mb-2"></div>
          <div className="h-4 bg-surface rounded w-1/3"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
          <h2 className="text-red-400 font-semibold mb-2">Error</h2>
          <p className="text-red-300">{error}</p>
          <button
            onClick={() => router.back()}
            className="mt-4 px-4 py-2 bg-surface hover:bg-surface-hover rounded-lg text-sm transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-6">
        <div className="text-center py-12">
          <h2 className="text-xl font-semibold text-text-primary mb-2">Project Not Found</h2>
          <p className="text-text-secondary mb-4">The project you're looking for doesn't exist or you don't have access to it.</p>
          <Link
            href="/projects"
            className="px-4 py-2 bg-brand-primary hover:bg-brand-primary/80 rounded-lg text-white text-sm transition-colors"
          >
            Back to Projects
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link
              href="/projects"
              className="text-text-secondary hover:text-text-primary transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </Link>
            <h1 className="text-2xl font-bold text-text-primary">{project.name}</h1>
          </div>
          {project.description && (
            <p className="text-text-secondary">{project.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
            project.status === 'active' 
              ? 'bg-green-500/10 text-green-400' 
              : 'bg-gray-500/10 text-gray-400'
          }`}>
            {project.status || 'active'}
          </span>
        </div>
      </div>

      {/* Project Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <div className="bg-surface border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-secondary mb-1">Slug</h3>
          <p className="text-text-primary font-mono">{project.slug || '-'}</p>
        </div>
        <div className="bg-surface border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-secondary mb-1">Created</h3>
          <p className="text-text-primary">
            {project.created_at ? new Date(project.created_at).toLocaleDateString() : '-'}
          </p>
        </div>
        <div className="bg-surface border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-secondary mb-1">Organization</h3>
          <p className="text-text-primary">{currentOrg?.name || '-'}</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Link
            href={`/incidents?project_id=${project.id}`}
            className="flex flex-col items-center p-4 bg-background hover:bg-surface-hover rounded-lg transition-colors border border-border"
          >
            <svg className="w-8 h-8 text-red-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="text-sm text-text-primary">Incidents</span>
          </Link>
          <Link
            href={`/groups?project_id=${project.id}`}
            className="flex flex-col items-center p-4 bg-background hover:bg-surface-hover rounded-lg transition-colors border border-border"
          >
            <svg className="w-8 h-8 text-blue-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span className="text-sm text-text-primary">Groups</span>
          </Link>
          <Link
            href={`/services?project_id=${project.id}`}
            className="flex flex-col items-center p-4 bg-background hover:bg-surface-hover rounded-lg transition-colors border border-border"
          >
            <svg className="w-8 h-8 text-purple-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
            </svg>
            <span className="text-sm text-text-primary">Services</span>
          </Link>
          <Link
            href={`/schedules?project_id=${project.id}`}
            className="flex flex-col items-center p-4 bg-background hover:bg-surface-hover rounded-lg transition-colors border border-border"
          >
            <svg className="w-8 h-8 text-green-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-sm text-text-primary">Schedules</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
