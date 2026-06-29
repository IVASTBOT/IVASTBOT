interface WarningBannerProps {
  warnings?: string[];
  compact?: boolean;
}

export function WarningBanner({ warnings = [], compact }: WarningBannerProps) {
  if (!warnings.length) return null;
  return <div className={compact ? "warning-banner compact" : "warning-banner"}>{warnings.join(" ")}</div>;
}
