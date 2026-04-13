import React, { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  chartName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ChartErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[ChartErrorBoundary] ${this.props.chartName ?? 'Chart'} crashed:`, error, info);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full min-h-[200px] rounded-xl border border-red-500/30 bg-red-900/10 p-6 text-center">
          <svg className="w-10 h-10 text-red-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <p className="text-sm font-medium text-red-300 mb-1">
            {this.props.chartName ?? 'Chart'} failed to render
          </p>
          <p className="text-xs text-gray-400 mb-4 max-w-xs">
            {this.state.error?.message ?? 'An unexpected error occurred'}
          </p>
          <button
            onClick={this.handleRetry}
            className="text-xs px-3 py-1.5 rounded-md bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
