import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="notfound">
      <div className="notfound-code">404</div>
      <div className="notfound-title">Page not found</div>
      <div className="notfound-desc">
        The page you are looking for does not exist or has been moved. Check the URL or return to the dashboard.
      </div>
      <Link to="/" className="btn btn-primary" style={{ marginTop: 18 }}>
        Go back home
      </Link>
    </div>
  )
}
