'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '../../../../lib/api';
import { useAuth } from '../../../../contexts/AuthContext';

export default function OrganizationProjectsPage() {
  const params = useParams();
  const { session } = useAuth();
  const [projects, setProjects] = useState([]);
  const [organization, setOrganization] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!session?.access_token || !params.id) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        apiClient.setToken(session.access_token);

        // Fetch organization details
        const orgData = await apiClient.getOrganization(params.id);
        setOrganization(orgData);

        // Fetch projects for this organization
        const projectsData = await apiClient.getOrgProjects(params.id);
        // Handle null/undefined projects (Go nil slice serializes to null)
        setProjects(Array.isArray(projectsData?.projects) ? projectsData.projects : []);
        setError(null);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [params.id, session]);

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-surface rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-40 bg-surface rounded-lg"></div>
            ))}
          </div>
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
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link
            href="/organizations"
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">
              {organization?.name || 'Organization'} - Projects
            </h1>
            <p className="text-text-secondary text-sm">
              {projects.length} project{projects.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <Link
          href={`/organizations/${params.id}/projects/new`}
          className="px-4 py-2 bg-brand-primary hover:bg-brand-primary/80 rounded-lg text-white text-sm font-medium transition-colors"
        >
          Create Project
        </Link>
      </div>

      {/* Projects Grid */}
      {projects.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-12 text-center">
          <svg className="w-12 h-12 mx-auto text-text-muted mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Projects</h3>
          <p className="text-text-secondary mb-4">This organization has no projects yet.</p>
          <Link
            href={`/organizations/${params.id}/projects/new`}
            className="inline-flex items-center px-4 py-2 bg-brand-primary hover:bg-brand-primary/80 rounded-lg text-white text-sm font-medium transition-colors"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create First Project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="bg-surface border border-border rounded-lg p-6 hover:border-brand-primary/50 hover:shadow-lg transition-all group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-brand-primary/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-brand-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  project.status === 'active' 
                    ? 'bg-green-500/10 text-green-400' 
                    : 'bg-gray-500/10 text-gray-400'
                }`}>
                  {project.status || 'active'}
                </span>
              </div>
              <h3 className="text-lg font-semibold text-text-primary group-hover:text-brand-primary transition-colors mb-1">
                {project.name}
              </h3>
              {project.description && (
                <p className="text-text-secondary text-sm line-clamp-2 mb-3">
                  {project.description}
                </p>
              )}
              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>Slug: {project.slug || '-'}</span>
                <span>{project.created_at ? new Date(project.created_at).toLocaleDateString() : ''}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
