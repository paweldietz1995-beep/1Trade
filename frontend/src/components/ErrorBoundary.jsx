import React, { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('🚨 Runtime Error:', error);
    console.error('Component Stack:', errorInfo?.componentStack);
    this.setState({ error, errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
          <div className="bg-[#0A0A0A] border border-neon-red/30 rounded-sm p-8 max-w-md w-full text-center">
            <div className="w-16 h-16 rounded-full bg-neon-red/20 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-neon-red" />
            </div>
            <h2 className="text-xl font-heading font-bold text-neon-red mb-2">
              App Error
            </h2>
            <p className="text-muted-foreground mb-6">
              Something went wrong. Please try reloading the page.
            </p>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="bg-[#050505] p-3 rounded-sm mb-4 text-left overflow-auto max-h-40">
                <p className="text-xs font-mono text-neon-red">
                  {this.state.error.toString()}
                </p>
              </div>
            )}
            <div className="flex gap-3 justify-center">
              <Button
                onClick={this.handleReset}
                variant="outline"
                className="border-[#1E293B]"
              >
                Try Again
              </Button>
              <Button
                onClick={this.handleReload}
                className="bg-neon-violet hover:bg-neon-violet/90"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Reload Page
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
