'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '../../../../lib/api';
import { useAuth } from '../../../../contexts/AuthContext';
import { useOrg } from '../../../../contexts/OrgContext';

const SEVERITY_COLORS = {
  critical: 'bg-red-500/10 text-red-400 border-red-500/20',
  error: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

const STATUS_COLORS = {
  triggered: 'bg-red-500/10 text-red-400',
  acknowledged: 'bg-yellow-500/10 text-yellow-400',
  resolved: 'bg-green-500/10 text-green-400',
};

export default function ProjectIncidentsPage() {
  const params = useParams();
  const { session } = useAuth();
  const { currentOrg } = useOrg();
  const [incidents, setIncidents] = useState([]);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!session?.access_token || !currentOrg?.id || !params.id) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        apiClient.setToken(session.access_token);

        // Fetch project details
        const projectData = await apiClient.getProject(params.id);
        setProject(projectData);

        // Fetch incidents for this project
        const incidentsData = await apiClient.getIncidents('', {
          org_id: currentOrg.id,
          project_id: params.id,
        });
        setIncidents(incidentsData.incidents || []);
        setError(null);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [params.id, session, currentOrg?.id]);

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-surface rounded w-1/4"></div>
          <div className="h-64 bg-surface rounded"></div>
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
            href={`/projects/${params.id}`}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">
              {project?.name || 'Project'} - Incidents
            </h1>
            <p className="text-text-secondary text-sm">
              {incidents.length} incident{incidents.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <Link
          href="/incidents/new"
          className="px-4 py-2 bg-brand-primary hover:bg-brand-primary/80 rounded-lg text-white text-sm font-medium transition-colors"
        >
          Create Incident
        </Link>
      </div>

      {/* Incidents List */}
      {incidents.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-12 text-center">
          <svg className="w-12 h-12 mx-auto text-text-muted mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Incidents</h3>
          <p className="text-text-secondary mb-4">This project has no incidents yet.</p>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-background">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Incident
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Severity
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Created
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Assigned To
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {incidents.map((incident) => (
                <tr key={incident.id} className="hover:bg-surface-hover transition-colors">
                  <td className="px-4 py-4">
                    <Link
                      href={`/incidents/${incident.id}`}
                      className="text-text-primary hover:text-brand-primary font-medium"
                    >
                      {incident.title}
                    </Link>
                    {incident.description && (
                      <p className="text-text-secondary text-sm mt-1 line-clamp-1">
                        {incident.description}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium border ${SEVERITY_COLORS[incident.severity] || SEVERITY_COLORS.info}`}>
                      {incident.severity || 'unknown'}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[incident.status] || STATUS_COLORS.triggered}`}>
                      {incident.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-text-secondary text-sm">
                    {formatDate(incident.created_at)}
                  </td>
                  <td className="px-4 py-4 text-text-secondary text-sm">
                    {incident.assigned_to_name || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
