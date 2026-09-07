import { ReactNode, type CSSProperties } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: boolean;
  style?: CSSProperties;
}

export function Card({ children, className = '', padding = true, style }: CardProps) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-navy-100 ${padding ? 'p-6' : ''} ${className}`} style={style}>
      {children}
    </div>
  );
}

export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'default';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  const variants: Record<string, string> = {
    success: 'bg-green-100 text-green-700',
    warning: 'bg-amber-100 text-amber-700',
    danger: 'bg-red-100 text-red-700',
    info: 'bg-blue-100 text-blue-700',
    default: 'bg-navy-100 text-navy-600',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}

export function Button({ children, onClick, variant = 'primary', size = 'md', disabled = false, className = '', type = 'button' }: ButtonProps) {
  const variants: Record<string, string> = {
    primary: 'bg-saffron-500 hover:bg-saffron-600 text-white shadow-sm',
    secondary: 'bg-navy-600 hover:bg-navy-700 text-white',
    danger: 'bg-red-500 hover:bg-red-600 text-white',
    ghost: 'bg-transparent hover:bg-navy-50 text-navy-600',
  };
  const sizes: Record<string, string> = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 ${variants[variant]} ${sizes[size]} ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${className}`}
    >
      {children}
    </button>
  );
}

interface ProgressBarProps {
  value: number;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  showLabel?: boolean;
  className?: string;
}

export function ProgressBar({ value, max = 5, size = 'md', color, showLabel = true, className = '' }: ProgressBarProps) {
  const percentage = Math.min(100, (value / max) * 100);
  const heights: Record<string, string> = { sm: 'h-1.5', md: 'h-2.5', lg: 'h-4' };
  let barColor = color || 'bg-navy-500';
  if (!color) {
    if (percentage >= 80) barColor = 'bg-green-500';
    else if (percentage >= 60) barColor = 'bg-saffron-500';
    else if (percentage >= 40) barColor = 'bg-amber-500';
    else barColor = 'bg-red-500';
  }

  return (
    <div className={className}>
      <div className={`w-full bg-navy-100 rounded-full ${heights[size]}`}>
        <div className={`${barColor} ${heights[size]} rounded-full transition-all duration-700 ease-out`} style={{ width: `${percentage}%` }} />
      </div>
      {showLabel && (
        <div className="flex justify-between mt-1 text-xs text-navy-400">
          <span>{value} / {max}</span>
          <span>{Math.round(percentage)}%</span>
        </div>
      )}
    </div>
  );
}

interface TooltipProps {
  text: string;
  children: ReactNode;
}

export function Tooltip({ text, children }: TooltipProps) {
  return (
    <div className="relative group inline-flex">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-navy-800 text-white text-xs rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 whitespace-nowrap z-50 pointer-events-none">
        {text}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-navy-800" />
      </div>
    </div>
  );
}

interface SelectProps {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}

export function Select({ label, value, onChange, options, className = '' }: SelectProps) {
  return (
    <div className={className}>
      {label && <label className="block text-sm font-medium text-navy-700 mb-1">{label}</label>}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white text-navy-800 focus:ring-2 focus:ring-saffron-400 focus:border-saffron-400 outline-none"
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

interface InputProps {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
  className?: string;
}

export function Input({ label, value, onChange, placeholder, type = 'text', disabled = false, className = '' }: InputProps) {
  return (
    <div className={className}>
      {label && <label className="block text-sm font-medium text-navy-700 mb-1">{label}</label>}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white text-navy-800 focus:ring-2 focus:ring-saffron-400 focus:border-saffron-400 outline-none"
      />
    </div>
  );
}

interface EmptyStateProps {
  icon: string;
  title: string;
  description: string;
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <span className="text-4xl mb-3">{icon}</span>
      <h3 className="text-lg font-semibold text-navy-700 mb-1">{title}</h3>
      <p className="text-sm text-navy-400 max-w-sm">{description}</p>
    </div>
  );
}
