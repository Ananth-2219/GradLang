import React from 'react';
import { AlertCircle, FileWarning } from 'lucide-react';

export default function ErrorBanner({ error }) {
  if (!error) return null;

  const { errorType, phase, message, line, column } = error;

  return (
    <div className="error-banner">
      <div className="error-header">
        <AlertCircle size={16} />
        <span>COMPILER DIAGNOSTIC [{phase || 'Pipeline'} Phase] &mdash; {errorType}</span>
        {line !== null && line !== undefined && (
          <span
            style={{
              background: '#f43f5e',
              color: '#fff',
              fontSize: '0.7rem',
              fontWeight: 700,
              padding: '0.1rem 0.4rem',
              borderRadius: '3px',
              marginLeft: 'auto',
            }}
          >
            LINE {line}{column ? ` : COL ${column}` : ''}
          </span>
        )}
      </div>
      <div className="error-message">
        {message}
      </div>
    </div>
  );
}
