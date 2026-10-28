import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      message="That page does not exist."
      action={<Link to="/" className="btn-yellow">Start an investigation</Link>}
    />
  );
}
