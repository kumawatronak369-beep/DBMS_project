import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button.jsx'
import { EmptyState } from '../components/ui/States.jsx'
import { usePageTitle } from '../hooks/usePageTitle.js'

export default function NotFoundPage() {
  usePageTitle('Page not found')
  return (
    <EmptyState
      icon={Compass}
      title="Page not found"
      hint="The page you are looking for does not exist."
      action={
        <Link to="/dashboard">
          <Button>Back to dashboard</Button>
        </Link>
      }
    />
  )
}
