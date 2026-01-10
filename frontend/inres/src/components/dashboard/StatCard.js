export default function StatCard({ 
  title, 
  value, 
  subtitle, 
  icon, 
  trend, 
  className = "", 
  iconColor = "blue",
  prominent = false,  // Makes card visually dominant
  showAlert = false   // Shows red dot indicator
}) {
  // Brand-style gradient color schemes (default: desaturated)
  const iconColorSchemes = {
    blue: "bg-gradient-to-br from-primary-400/90 to-primary-500/90",
    purple: "bg-gradient-to-br from-purple-400/90 to-purple-500/90",
    green: "bg-gradient-to-br from-success-400/90 to-success-500/90",
    orange: "bg-gradient-to-br from-warning-400/90 to-warning-500/90",
    red: "bg-gradient-to-br from-red-400/90 to-red-500/90",
    indigo: "bg-gradient-to-br from-indigo-400/90 to-indigo-500/90",
    pink: "bg-gradient-to-br from-pink-400/90 to-pink-500/90",
    cyan: "bg-gradient-to-br from-accent-400/90 to-accent-500/90",
    amber: "bg-gradient-to-br from-amber-400/90 to-amber-500/90",
    emerald: "bg-gradient-to-br from-emerald-400/90 to-emerald-500/90",
  };

  // More saturated colors for prominent cards
  const prominentIconSchemes = {
    blue: "bg-gradient-to-br from-primary-500 to-primary-600",
    red: "bg-gradient-to-br from-red-500 to-red-600",
    amber: "bg-gradient-to-br from-amber-500 to-amber-600",
  };

  // Glow colors for icons
  const glowColors = {
    blue: "shadow-[0_0_16px_rgba(0,102,204,0.25)]",
    cyan: "shadow-[0_0_16px_rgba(0,188,212,0.25)]",
    green: "shadow-[0_0_16px_rgba(76,175,80,0.25)]",
    emerald: "shadow-[0_0_16px_rgba(16,185,129,0.25)]",
    red: "shadow-[0_0_16px_rgba(244,67,54,0.25)]",
    orange: "shadow-[0_0_16px_rgba(255,152,0,0.25)]",
  };

  // Stronger glow for prominent cards
  const prominentGlow = {
    blue: "shadow-[0_0_24px_rgba(0,102,204,0.4)]",
    red: "shadow-[0_0_24px_rgba(244,67,54,0.4)]",
  };

  const iconScheme = prominent 
    ? (prominentIconSchemes[iconColor] || iconColorSchemes[iconColor] || iconColorSchemes.blue)
    : (iconColorSchemes[iconColor] || iconColorSchemes.blue);

  const iconGlow = prominent
    ? (prominentGlow[iconColor] || glowColors[iconColor] || glowColors.blue)
    : (glowColors[iconColor] || glowColors.blue);

  return (
    <div className={`
      relative overflow-hidden
      bg-white dark:bg-navy-800/50 backdrop-blur-sm
      rounded-xl border border-gray-200 dark:border-navy-600/50
      p-5 transition-all duration-300
      hover:border-primary-500/30 hover:shadow-lg
      group
      ${className}
    `}>
      {/* Subtle gradient overlay on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      
      <div className="relative flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{title}</p>
          <div className="flex items-center gap-2 mt-2">
            <p className={`font-bold text-gray-900 dark:text-white ${prominent ? 'text-4xl' : 'text-3xl'}`}>
            {value}
          </p>
            {/* Alert indicator dot */}
            {showAlert && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
              </span>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className={`
            p-3 rounded-xl text-white
            ${iconScheme}
            ${iconGlow}
            transition-transform group-hover:scale-110
          `}>
            {icon}
          </div>
        )}
      </div>
      
      {trend && (
        <div className="relative mt-4 pt-3 border-t border-gray-200 dark:border-navy-700/50 flex items-center text-sm">
          <span className={`
            inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium
            ${trend.type === 'up' 
              ? 'bg-success-500/20 text-success-500' 
              : trend.type === 'down' 
                ? 'bg-danger-500/20 text-danger-500' 
                : 'bg-gray-200 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400'
            }
          `}>
            {trend.type === 'up' && (
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            )}
            {trend.type === 'down' && (
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            )}
            {trend.value}
          </span>
          <span className="text-gray-500 dark:text-gray-500 ml-2">{trend.label}</span>
        </div>
      )}
    </div>
  );
}
