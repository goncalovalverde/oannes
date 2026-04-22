import { useToast } from '../context/ToastContext';

export interface APIErrorResponse {
  error: boolean;
  message: string;
  error_code: string;
  path?: string;
}

/**
 * Hook for handling API errors and displaying them as toasts.
 * 
 * Usage:
 * const { handleError } = useAPIErrorHandler();
 * try {
 *   await fetchSomething();
 * } catch (err) {
 *   handleError(err);
 * }
 */
export function useAPIErrorHandler() {
  const { showToast } = useToast();

  const handleError = (error: unknown) => {
    let message = 'An unexpected error occurred. Please try again.';
    let code = 'UNKNOWN_ERROR';

    if (error instanceof Response) {
      // Handle Response objects
      code = error.status.toString();
      if (error.status === 404) {
        message = 'Resource not found. Please check the project and try again.';
      } else if (error.status === 429) {
        message = 'Rate limit exceeded. Please wait a moment and try again.';
      } else if (error.status === 422) {
        message = 'Invalid data. Please check your input and try again.';
      } else if (error.status === 500) {
        message = 'Server error. Please try again later.';
      }
    } else if (error instanceof Error) {
      message = error.message;
      code = error.name;
    } else if (typeof error === 'object' && error !== null) {
      const err = error as APIErrorResponse;
      if (err.message) {
        message = err.message;
        code = err.error_code || 'ERROR';
      } else if (err.error) {
        message = 'An error occurred.';
      }
    }

    console.error(`[API Error] ${code}: ${message}`, error);
    showToast(message, 'error', 5000);
  };

  return { handleError };
}
