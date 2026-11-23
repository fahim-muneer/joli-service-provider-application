export default function ErrorMessage({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="alert alert--error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn btn--small btn--ghost" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
