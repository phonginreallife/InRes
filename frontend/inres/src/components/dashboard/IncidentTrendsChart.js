'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import { apiClient } from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useOrg } from '../../contexts/OrgContext';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Time range options
const TIME_RANGES = [
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
];

// Chart color palette - vibrant and modern with glow effects
const COLORS = {
  triggered: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgb(239, 68, 68)' },
  acknowledged: { bg: 'rgba(251, 191, 36, 0.8)', border: 'rgb(251, 191, 36)' },
  resolved: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgb(16, 185, 129)' },
  total: { bg: 'rgba(59, 130, 246, 0.15)', border: 'rgb(59, 130, 246)' },
  // Severity colors - more vibrant
  critical: 'rgba(239, 68, 68, 0.9)',
  high: 'rgba(249, 115, 22, 0.9)',
  error: 'rgba(156, 163, 175, 0.9)',
  medium: 'rgba(59, 130, 246, 0.9)',
  low: 'rgba(34, 197, 94, 0.9)',
  unknown: 'rgba(156, 163, 175, 0.85)',
};

// CSS styles for dashboard
const styles = `
  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  @keyframes countUp {
    from {
      opacity: 0;
      transform: scale(0.5);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }
  
  .trends-card {
    animation: fadeInUp 0.5s ease-out forwards;
  }
  
  .trends-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.15);
  }
  
  .metric-card {
    position: relative;
    overflow: hidden;
  }
  
  .metric-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--accent-color, var(--color-primary-500));
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  
  .metric-card:hover::before {
    opacity: 1;
  }
  
  .metric-value {
    animation: countUp 0.6s ease-out;
  }
  
  .time-range-btn {
    position: relative;
    overflow: hidden;
  }
  
  .chart-container {
    position: relative;
  }
`;

export default function IncidentTrendsChart({ refreshKey = 0 }) {
  const { session } = useAuth();
  const { currentOrg, currentProject } = useOrg();
  const [timeRange, setTimeRange] = useState('7d');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [trends, setTrends] = useState(null);

  const fetchTrends = useCallback(async () => {
    if (!session?.access_token || !currentOrg?.id) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      apiClient.setToken(session.access_token);

      const data = await apiClient.getIncidentTrends(timeRange, {
        org_id: currentOrg.id,
        ...(currentProject?.id && { project_id: currentProject.id }),
      });

      setTrends(data);
    } catch (err) {
      console.error('Failed to fetch incident trends:', err);
      setError('Failed to load trends data');
    } finally {
      setLoading(false);
    }
  }, [session, currentOrg?.id, currentProject?.id, timeRange]);

  useEffect(() => {
    fetchTrends();
  }, [fetchTrends, refreshKey]);

  // Line chart config for incident volume over time - vibrant glowing lines
  const lineChartData = {
    labels: trends?.daily_counts?.map(d => {
      const date = new Date(d.date);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }) || [],
    datasets: [
      {
        label: 'Total',
        data: trends?.daily_counts?.map(d => d.total) || [],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: (context) => {
          const ctx = context.chart.ctx;
          const gradient = ctx.createLinearGradient(0, 0, 0, 200);
          gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
          gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');
          return gradient;
        },
        fill: true,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 9,
        pointBackgroundColor: 'rgb(59, 130, 246)',
        pointBorderColor: '#fff',
        pointBorderWidth: 3,
        borderWidth: 4,
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(59, 130, 246)',
        pointHoverBorderWidth: 3,
      },
      {
        label: 'Triggered',
        data: trends?.daily_counts?.map(d => d.triggered) || [],
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'transparent',
        borderWidth: 3,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointBackgroundColor: 'rgb(239, 68, 68)',
        pointBorderColor: '#fff',
        pointBorderWidth: 3,
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(239, 68, 68)',
        pointHoverBorderWidth: 3,
      },
      {
        label: 'Resolved',
        data: trends?.daily_counts?.map(d => d.resolved) || [],
        borderColor: 'rgb(16, 185, 129)',
        backgroundColor: 'transparent',
        borderWidth: 3,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointBackgroundColor: 'rgb(16, 185, 129)',
        pointBorderColor: '#fff',
        pointBorderWidth: 3,
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(16, 185, 129)',
        pointHoverBorderWidth: 3,
      },
    ],
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    animation: {
      duration: 1000,
      easing: 'easeOutQuart',
    },
    hover: {
      mode: 'nearest',
      intersect: true,
      animationDuration: 200,
    },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 20,
          font: { size: 12, weight: '500' },
        },
      },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleFont: { size: 14, weight: '600' },
        bodyFont: { size: 13 },
        padding: 14,
        cornerRadius: 10,
        displayColors: true,
        boxPadding: 6,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { 
          font: { size: 11, weight: '500' },
          color: 'rgb(107, 114, 128)',
        },
      },
      y: {
        beginAtZero: true,
        grid: { 
          color: 'rgba(107, 114, 128, 0.08)',
          drawBorder: false,
        },
        ticks: { 
          font: { size: 11 },
          color: 'rgb(107, 114, 128)',
          stepSize: 2,
          padding: 8,
        },
        border: {
          display: false,
        },
      },
    },
  };

  // Doughnut chart for severity breakdown - vibrant modern style
  const severityLabels = Object.keys(trends?.by_severity || {});
  const severityData = Object.values(trends?.by_severity || {});
  const totalSeverity = severityData.reduce((a, b) => a + b, 0);
  
  // Vibrant gradient-like colors for severity
  const severityColorMap = {
    critical: 'rgb(239, 68, 68)',
    high: 'rgb(249, 115, 22)', 
    medium: 'rgb(59, 130, 246)',
    low: 'rgb(34, 197, 94)',
    error: 'rgb(156, 163, 175)',
    unknown: 'rgb(107, 114, 128)',
  };
  const severityColors = severityLabels.map(s => severityColorMap[s.toLowerCase()] || severityColorMap.unknown);

  const doughnutChartData = {
    labels: severityLabels.map(s => s.charAt(0).toUpperCase() + s.slice(1)),
    datasets: [
      {
        data: severityData,
        backgroundColor: severityColors,
        borderColor: 'rgba(255, 255, 255, 0.8)',
        borderWidth: 3,
        hoverOffset: 12,
        hoverBorderWidth: 4,
        hoverBorderColor: '#fff',
        spacing: 2,
      },
    ],
  };

  // Center text plugin for doughnut
  const centerTextPlugin = {
    id: 'centerText',
    beforeDraw: (chart) => {
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      
      // Calculate the actual center of the doughnut (chart area, not canvas)
      const centerX = (chartArea.left + chartArea.right) / 2;
      const centerY = (chartArea.top + chartArea.bottom) / 2;
      
      ctx.save();
      const text = totalSeverity.toString();
      const subText = 'Total';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      // Main number
      ctx.font = 'bold 28px system-ui';
      ctx.fillStyle = '#1f2937';
      ctx.fillText(text, centerX, centerY - 8);
      // Sub label
      ctx.font = '12px system-ui';
      ctx.fillStyle = '#6b7280';
      ctx.fillText(subText, centerX, centerY + 14);
      ctx.restore();
    },
  };

  const doughnutChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    animation: {
      animateRotate: true,
      animateScale: true,
      duration: 800,
      easing: 'easeOutQuart',
    },
    plugins: {
      legend: {
        position: 'right',
        labels: {
          usePointStyle: true,
          pointStyle: 'circle',
          padding: 16,
          font: { size: 12, weight: '500' },
          color: '#374151',
        },
      },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleFont: { size: 14, weight: '600' },
        bodyFont: { size: 13 },
        padding: 14,
        cornerRadius: 10,
        displayColors: true,
        boxPadding: 6,
        callbacks: {
          label: (context) => {
            const value = context.raw;
            const percentage = ((value / totalSeverity) * 100).toFixed(1);
            return ` ${value} incidents (${percentage}%)`;
          },
        },
      },
    },
  };

  // Bar chart for urgency breakdown - vibrant style
  const barChartData = {
    labels: ['High', 'Low'],
    datasets: [
      {
        label: 'Incidents',
        data: [trends?.by_urgency?.high || 0, trends?.by_urgency?.low || 0],
        backgroundColor: ['rgb(239, 68, 68)', 'rgb(34, 197, 94)'],
        hoverBackgroundColor: ['rgb(220, 38, 38)', 'rgb(22, 163, 74)'],
        borderRadius: 8,
        barThickness: 32,
        borderSkipped: false,
      },
    ],
  };

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    animation: {
      duration: 800,
      easing: 'easeOutQuart',
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleFont: { size: 14, weight: '600' },
        bodyFont: { size: 13 },
        padding: 14,
        cornerRadius: 10,
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: { color: 'rgba(107, 114, 128, 0.08)', drawBorder: false },
        ticks: { font: { size: 11 }, color: 'rgb(107, 114, 128)' },
        border: { display: false },
      },
      y: {
        grid: { display: false },
        ticks: { font: { size: 12, weight: '600' }, color: '#374151' },
        border: { display: false },
      },
    },
  };

  if (loading) {
    return (
      <>
        <style>{styles}</style>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gray-200 dark:bg-gray-700 animate-pulse"></div>
            <div className="space-y-1.5">
              <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
              <div className="h-3 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 h-52 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse"></div>
            <div className="h-52 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse"></div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse"></div>
            ))}
          </div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <style>{styles}</style>
        <div className="bg-gradient-to-r from-red-50 to-rose-50 dark:from-red-900/20 dark:to-rose-900/20 border border-red-200/50 dark:border-red-800/50 rounded-2xl p-6 shadow-lg">
          <div className="flex items-center gap-3 text-red-700 dark:text-red-400">
            <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/50 flex items-center justify-center">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="font-semibold">Failed to load trends</p>
              <span className="text-sm opacity-80">{error}</span>
            </div>
          </div>
        </div>
      </>
    );
  }

  const hasData = trends?.total_incidents > 0;

  return (
    <>
      <style>{styles}</style>
      <div className="space-y-4">
        {/* Header with time range selector */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-500 flex items-center justify-center shadow-lg shadow-primary-500/20">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Incident Trends
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {trends?.total_incidents || 0} incidents in the last {timeRange === '7d' ? '7 days' : timeRange === '30d' ? '30 days' : '90 days'}
              </p>
            </div>
          </div>

          {/* Time range buttons */}
          <div className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
            {TIME_RANGES.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setTimeRange(value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  timeRange === value
                    ? 'bg-primary-500 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

      {!hasData ? (
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-8 text-center border border-gray-200/50 dark:border-gray-700/50">
          <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">No incident data</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            No incidents recorded in the selected time period.
          </p>
        </div>
      ) : (
        <>
          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Main Line Chart - Incident Volume */}
            <div className="lg:col-span-2 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-800/30 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow duration-200">
              <h3 className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                Incidents Over Time
              </h3>
              <div className="h-44">
                <Line data={lineChartData} options={lineChartOptions} />
              </div>
            </div>

            {/* Severity Breakdown Doughnut */}
            <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-800/30 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow duration-200">
              <h3 className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-gradient-to-r from-red-500 via-orange-500 to-green-500"></span>
                By Severity
              </h3>
              <div className="h-44">
                {severityData.length > 0 ? (
                  <Doughnut data={doughnutChartData} options={doughnutChartOptions} plugins={[centerTextPlugin]} />
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-gray-400">
                    No severity data
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Metrics Row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* MTTA Card */}
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-6 h-6 rounded-lg bg-primary-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">MTTA</span>
              </div>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {trends?.metrics?.mtta_avg_minutes || 'N/A'}
                {trends?.metrics?.mtta_avg_minutes !== 'N/A' && (
                  <span className="text-xs font-normal text-gray-400 ml-0.5">min</span>
                )}
              </p>
            </div>

            {/* MTTR Card */}
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-6 h-6 rounded-lg bg-primary-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">MTTR</span>
              </div>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {trends?.metrics?.mttr_avg_minutes || 'N/A'}
                {trends?.metrics?.mttr_avg_minutes !== 'N/A' && (
                  <span className="text-xs font-normal text-gray-400 ml-0.5">min</span>
                )}
              </p>
            </div>

            {/* Acknowledged Card */}
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-6 h-6 rounded-lg bg-primary-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">Ack&apos;d</span>
              </div>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {trends?.metrics?.acknowledged_count || 0}
              </p>
            </div>

            {/* Resolved Card */}
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-6 h-6 rounded-lg bg-primary-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">Resolved</span>
              </div>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {trends?.metrics?.resolved_count || 0}
              </p>
            </div>
          </div>

          {/* Top Services */}
          {trends?.by_service?.length > 0 && (
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-3">
                Top Services
              </h3>
              <div className="space-y-2">
                {trends.by_service.slice(0, 3).map((service, idx) => {
                  const maxCount = Math.max(...trends.by_service.map(s => s.count));
                  const percentage = (service.count / maxCount) * 100;
                  return (
                    <div key={service.service_id || idx} className="flex items-center gap-2">
                      <span className="text-xs text-gray-600 dark:text-gray-400 truncate flex-1">
                        {service.service_name}
                      </span>
                      <div className="w-20 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-primary-500 rounded-full"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-gray-900 dark:text-white w-6 text-right">
                        {service.count}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
    </>
  );
}
