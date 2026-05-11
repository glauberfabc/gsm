import { Component } from 'react';
import { AlertTriangle } from 'lucide-react';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 bg-red-50 border-2 border-red-200 rounded-xl text-center">
          <AlertTriangle size={48} className="mx-auto text-red-500 mb-4"/>
          <h3 className="text-lg font-bold text-red-700">Ocorreu um erro</h3>
          <p className="text-sm text-red-600 mt-2">{this.state.error?.message || 'Erro desconhecido'}</p>
          <button 
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-4 px-6 py-2 bg-red-600 text-white rounded-lg font-bold"
          >
            Tentar Novamente
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
